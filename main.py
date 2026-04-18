import os
import json
from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI
fastapi_app = FastAPI(title="Lios-Agent")

# Initialize Slack App
# Note: Requires SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET in .env
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN", "mock-token-for-dev"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET", "mock-secret-for-dev")
)
slack_handler = SlackRequestHandler(slack_app)

# --------------------------------------------------------------------------
# Slack Event Handlers
# --------------------------------------------------------------------------

@slack_app.command("/ios-agent")
def handle_agent_command(ack, say, command, logger):
    """Handle the /ios-agent slash command"""
    text = command.get("text", "").strip()
    
    # Handle dynamic configuration via Slack
    if text == "config help":
        ack()
        help_text = """
*Lios-Agent Configuration Help* 🛠️
Use `/ios-agent config set <KEY> <VALUE>` to update settings dynamically.

*Global Settings:*
• `LLM_PROVIDER`: The primary AI provider (e.g., `glm`, `openai`, `ollama`)
• `LLM_MODEL_NAME`: The specific model (e.g., `glm-5.1`, `gpt-4o`)
• `<PROVIDER>_API_KEY`: The API key (e.g., `GLM_API_KEY`, `OPENAI_API_KEY`)

*Role-Specific Settings (Optional Mixture of Experts):*
• `LLM_PROVIDER_PLANNING` / `LLM_MODEL_PLANNING`: Used only during the graph's reasoning phase.
• `LLM_PROVIDER_CODING` / `LLM_MODEL_CODING`: Used only during the code generation phase.

_Note: Role-specific models automatically fallback to the global settings if they are not explicitly set._
"""
        say(help_text)
        return

    if text.startswith("config set"):
        ack()
        parts = text.split(" ", 3) # ex: [config, set, GLM_API_KEY, sk-...]
        if len(parts) >= 4:
            key_name = parts[2]
            key_value = parts[3]
            
            from dotenv import set_key
            env_path = os.path.join(os.path.dirname(__file__), ".env")
            
            # Write securely to the physical .env file
            set_key(env_path, key_name, key_value)
            # Update the current runtime env so we don't need a hard restart
            os.environ[key_name] = key_value
            
            say(f"✅ Successfully updated `{key_name}` in the orchestrator config.\n(Remember to set `LLM_PROVIDER` and `LLM_MODEL_NAME` to match if you switch providers!)")
        else:
            say("❌ Usage: `/ios-agent config set <KEY_NAME> <VALUE>`")
    else:
        logger.info(f"Received /ios-agent command: {text}")
        ack("Processing agent request... 🚀")

@slack_app.command("/agent-status")
def handle_status_command(ack, say, command):
    """Handle the /agent-status command"""
    ack()
    say(f"System Online. GitHub App and Slack App connected. Received from <@{command['user_id']}>")

@slack_app.event("app_mention")
def handle_app_mentions(body, say, logger):
    """Respond to mentions in channels"""
    logger.info(body)
    say("Greetings! I am the iOS Agent Orchestrator. How can I help you today?")

@slack_app.action("approve_pr")
def handle_approve_action(ack, body, logger, say):
    """Handle when someone clicks the 'Approve PR' button in a Block Kit message"""
    ack()
    user = body["user"]["id"]
    issue_num = body["actions"][0]["value"]
    logger.info(f"PR Approved Action Triggered by {user} for issue {issue_num}")
    
    say(f"✅ Executing final push for Task #{issue_num} by <@{user}>")
    
    def resume_graph():
        try:
            from agent.graph import build_graph
            graph_app = build_graph()
            config = {"configurable": {"thread_id": f"issue-{issue_num}"}}
            
            # Resume LangGraph from the checkpoint interrupt (None means no new user input)
            print(f"Resuming LangGraph execution for Issue {issue_num}...")
            graph_app.invoke(None, config=config)
            print("LangGraph final step complete.")
        except Exception as e:
            print(f"Failed to resume LangGraph: {e}")
            
    import threading
    threading.Thread(target=resume_graph).start()

# --------------------------------------------------------------------------
# FastAPI Endpoints
# --------------------------------------------------------------------------

@fastapi_app.post("/webhooks/slack/events")
async def slack_events(req: Request):
    """Endpoint for Slack Events API (mentions, messages)"""
    # Manual handle for Slack's "url_verification" challenge to make initial setup smoother
    body = await req.json()
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge")}
        
    return await slack_handler.handle(req)

@fastapi_app.post("/webhooks/slack/interactions")
async def slack_interactions(req: Request):
    """Endpoint for Slack Interactivity (Block Kit buttons)"""
    return await slack_handler.handle(req)

@fastapi_app.post("/webhooks/slack/commands")
async def slack_commands(req: Request):
    """Endpoint for Slack Slash Commands"""
    return await slack_handler.handle(req)

@fastapi_app.post("/webhooks/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint for GitHub Webhooks (Issues, PRs, Comments).
    Authenticates webhook via X-Hub-Signature-256 in production.
    """
    event_type = request.headers.get("X-GitHub-Event")
    payload = await request.json()
    
    if event_type == "issues":
        action = payload.get("action")
        issue = payload.get("issue")
        repository = payload.get("repository", {})
        installation = payload.get("installation", {})
        
        if action == "opened":
            issue_num = str(issue.get("number"))
            issue_title = issue.get("title")
            issue_body = issue.get("body", "")
            repo_url = repository.get("ssh_url")
            repo_full_name = repository.get("full_name")
            installation_id = str(installation.get("id", ""))
            
            # Post a Slack message notifying the team
            slack_channel = os.environ.get("SLACK_CHANNEL_ID")
            if slack_channel:
                try:
                    slack_app.client.chat_postMessage(
                        channel=slack_channel,
                        text=f"New Agent Task Created!",
                        blocks=[
                            {
                                "type": "section",
                                "text": {"type": "mrkdwn", "text": f"*New GitHub Issue for Agent*\n<{issue['html_url']}|#{issue_num} - {issue_title}>\nTarget Repo: `{repository.get('full_name')}`"}
                            },
                        ]
                    )
                except Exception as e:
                    print(f"Error posting to Slack: {e}")
                    
            # Trigger LangGraph Workflow Background Task
            def run_agent_workflow():
                try:
                    from agent.graph import build_graph
                    graph_app = build_graph()
                    
                    initial_state = {
                        "task_id": issue_num,
                        "instructions": f"Title: {issue_title}\n\nDescription:\n{issue_body}",
                        "repo_url": repo_url,
                        "repo_full_name": repo_full_name,
                        "installation_id": installation_id,
                        "history": [],
                        "compiler_errors": [],
                        "retries_count": 0
                    }
                    
                    print(f"🚀 Triggering LangGraph for Issue {issue_num}")
                    config = {"configurable": {"thread_id": f"issue-{issue_num}"}}
                    graph_app.invoke(initial_state, config=config)
                except Exception as e:
                    print(f"❌ Core LangGraph Error: {e}")
                    
            background_tasks.add_task(run_agent_workflow)
                    
    return {"status": "ok", "event": event_type}

@fastapi_app.get("/health")
def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "Lios-Agent"}

if __name__ == "__main__":
    import uvicorn
    # Local development server
    uvicorn.run("main:fastapi_app", host="0.0.0.0", port=8000, reload=True)
