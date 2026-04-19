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
            
            # Verify checkpoint exists before attempting resume
            state = graph_app.get_state(config)
            if not state or not state.values:
                print(f"⚠️ No checkpoint found for issue-{issue_num}. Cannot resume.")
                return
                
            print(f"Resuming LangGraph execution for Issue {issue_num}...")
            print(f"  Checkpoint next steps: {state.next}")
            
            # MemorySaver is a plain Python dict — safe to access from any thread/loop
            import asyncio
            asyncio.run(graph_app.ainvoke(None, config=config))
            print("LangGraph final step complete.")
        except Exception as e:
            import traceback
            print(f"Failed to resume LangGraph: {e}")
            traceback.print_exc()
            
    import threading
    threading.Thread(target=resume_graph, daemon=True).start()

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
        
        if action in ["opened", "edited"]:
            issue_num = str(issue.get("number"))
            issue_title = issue.get("title")
            issue_body = issue.get("body", "")
            repo_url = repository.get("ssh_url")
            repo_full_name = repository.get("full_name")
            installation_id = str(installation.get("id", ""))
            
            if action == "opened":
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
            async def run_agent_workflow():
                try:
                    from agent.graph import build_graph
                    graph_app = build_graph()
                    config = {"configurable": {"thread_id": f"issue-{issue_num}"}}
                    
                    if action == "edited":
                        state = graph_app.get_state(config)
                        if state.next and state.next[0] == "await_clarification":
                            print(f"🚀 Resuming LangGraph Vetting for Edited Issue {issue_num}")
                            await graph_app.ainvoke({"instructions": f"Title: {issue_title}\n\nDescription:\n{issue_body}"}, config=config)
                        return
                    
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
                    await graph_app.ainvoke(initial_state, config=config)
                except Exception as e:
                    print(f"❌ Core LangGraph Error: {e}")
                    
            background_tasks.add_task(run_agent_workflow)
            
    elif event_type == "issue_comment":
        action = payload.get("action")
        comment = payload.get("comment", {})
        issue = payload.get("issue", {})
        
        # Prevent the agent from reacting to its own comments
        if comment.get("user", {}).get("type") == "Bot" or "bot" in comment.get("user", {}).get("login", "").lower():
            return {"status": "ignored"}
            
        body = comment.get("body", "").strip()
        issue_num = str(issue.get("number"))
        
        if action in ["created", "edited"]:
            async def resume_from_comment():
                try:
                    from agent.graph import build_graph
                    graph_app = build_graph()
                    config = {"configurable": {"thread_id": f"issue-{issue_num}"}}
                    state = graph_app.get_state(config)
                    
                    # Check if the user is approving the blueprint (paused at the 'router')
                    if "approve" in body.lower() and state.next and "router" in state.next:
                        print(f"🚀 Resuming LangGraph for Issue {issue_num} via GitHub comment approval")
                        await graph_app.ainvoke(None, config=config)
                    # Otherwise, check if they are clarifying a vague issue (paused at 'await_clarification')
                    elif state.next and "await_clarification" in state.next:
                        old_instructions = state.values.get("instructions", "")
                        new_instructions = old_instructions + f"\n\n[Developer Clarification]:\n{body}"
                        print(f"🚀 Resuming LangGraph Vetting for Issue {issue_num} with new clarification")
                        await graph_app.ainvoke({"instructions": new_instructions}, config=config)
                        
                except Exception as e:
                    print(f"❌ Core LangGraph Resume Error: {e}")
                    
            background_tasks.add_task(resume_from_comment)
            
    elif event_type == "pull_request_review_comment":
        # A human developer left an inline code review comment on the agent's PR.
        # We re-trigger the Coder -> Validator loop to address their feedback.
        action = payload.get("action")
        comment = payload.get("comment", {})
        pull_request = payload.get("pull_request", {})
        repository = payload.get("repository", {})
        installation = payload.get("installation", {})
        
        if action == "created":
            review_body = comment.get("body", "")
            diff_hunk = comment.get("diff_hunk", "")
            file_path = comment.get("path", "")
            pr_number = str(pull_request.get("number"))
            pr_branch = pull_request.get("head", {}).get("ref", "")
            repo_url = repository.get("ssh_url")
            repo_full_name = repository.get("full_name")
            installation_id = str(installation.get("id", ""))
            
            async def run_pr_review_fix():
                try:
                    from agent.graph import build_graph
                    from agent.tools import clone_isolated_workspace
                    import subprocess
                    
                    # 1. Clone workspace and checkout the existing PR branch
                    task_id = f"pr-review-{pr_number}"
                    clone_isolated_workspace(task_id, repo_url)
                    workspace_path = os.path.join(os.path.dirname(__file__), ".workspaces", task_id)
                    subprocess.run(["git", "fetch", "origin", pr_branch], cwd=workspace_path, check=True, capture_output=True)
                    subprocess.run(["git", "checkout", pr_branch], cwd=workspace_path, check=True, capture_output=True)
                    
                    # 2. Build a focused graph execution with the review as instructions
                    graph_app = build_graph()
                    review_instructions = f"""PR Review Fix Request:
File: {file_path}
Diff Context:
{diff_hunk}

Reviewer Comment: {review_body}

Fix the code in the file mentioned above based on the reviewer's feedback."""

                    initial_state = {
                        "task_id": task_id,
                        "instructions": review_instructions,
                        "repo_url": repo_url,
                        "repo_full_name": repo_full_name,
                        "installation_id": installation_id,
                        "workspace_path": workspace_path,
                        "current_branch": pr_branch,
                        "history": [],
                        "compiler_errors": [],
                        "retries_count": 0,
                        "mcp_context": ""
                    }
                    
                    print(f"🔄 PR Review Loop triggered for PR #{pr_number} on {file_path}")
                    config = {"configurable": {"thread_id": f"pr-review-{pr_number}"}}
                    await graph_app.ainvoke(initial_state, config=config)
                except Exception as e:
                    print(f"❌ PR Review Loop Error: {e}")
                    
            background_tasks.add_task(run_pr_review_fix)
            
    return {"status": "ok", "event": event_type}

@fastapi_app.get("/health")
def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "Lios-Agent"}

if __name__ == "__main__":
    import uvicorn
    # Local development server
    uvicorn.run("main:fastapi_app", host="0.0.0.0", port=8000, reload=True)
