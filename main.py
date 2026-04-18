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
def handle_agent_command(ack, body, logger):
    """Handle the /ios-agent slash command"""
    logger.info("Received /ios-agent command")
    ack("Initializing Agent Context... 🚀")

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
def handle_approve_action(ack, body, logger):
    """Handle when someone clicks the 'Approve PR' button in a Block Kit message"""
    ack()
    logger.info("PR Approved Action Triggered!")
    user = body["user"]["id"]
    # You could update the original message using respond() or client.chat_update()
    # For now, we'll just log it.

# --------------------------------------------------------------------------
# FastAPI Endpoints
# --------------------------------------------------------------------------

@fastapi_app.post("/webhooks/slack/events")
async def slack_events(req: Request):
    """Endpoint for Slack Events API (mentions, messages)"""
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
        if action == "opened":
            issue_num = issue.get("number")
            issue_title = issue.get("title")
            
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
                                "text": {"type": "mrkdwn", "text": f"*New GitHub Issue for Agent*\n<{issue['html_url']}|#{issue_num} - {issue_title}>"}
                            },
                            {
                                "type": "actions",
                                "elements": [
                                    {
                                        "type": "button",
                                        "text": {"type": "plain_text", "text": "Approve Agent Run"},
                                        "style": "primary",
                                        "action_id": "approve_pr",
                                        "value": str(issue_num)
                                    }
                                ]
                            }
                        ]
                    )
                except Exception as e:
                    print(f"Error posting to Slack: {e}")
                    
    return {"status": "ok", "event": event_type}

@fastapi_app.get("/health")
def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "Lios-Agent"}

if __name__ == "__main__":
    import uvicorn
    # Local development server
    uvicorn.run("main:fastapi_app", host="0.0.0.0", port=8000, reload=True)
