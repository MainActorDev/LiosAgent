# App Setup Guide (Phase 1)

This guide documents the procedures for configuring the GitHub and Slack Apps necessary for the Agentic Coding Orchestrator. 

## 1. GitHub App Setup

1. **Go to Developer Settings**: Navigate to `Settings` > `Developer settings` > `GitHub Apps` > `New GitHub App`.
2. **Basic Setup**: Provide a name (e.g., "Agentic-Orchestrator-Bot") and Homepage URL.
3. **Webhook Setup**:
   - Enable Webhooks.
   - Set the Payload URL to your ngrok URL: `https://<your-ngrok-url>.ngrok.io/webhooks/github`
   - Create a Webhook secret and add it to your local `.env` file as `GITHUB_WEBHOOK_SECRET`.
4. **Permissions**:
   - `Contents`: Read & Write
   - `Issues`: Read & Write
   - `Pull Requests`: Read & Write
   - `Metadata`: Read-only
5. **Event Subscriptions**: Subscribe to `Issues`, `Issue comment`, `Pull request`, and `Push`.
6. **Generate Private Key**: At the bottom of the page, generate a private key and download the `.pem` file. Place it securely.

## 2. Slack App Setup

1. **Go to Slack API**: Navigate to `api.slack.com/apps` and click `Create New App` > `From Scratch`.
2. **Basic Information**: Name it "iOS Agent Orchestrator" and select your target workspace.
3. **Slash Commands**:
   - Create `/ios-agent` pointing to `https://<your-ngrok-url>.ngrok.io/webhooks/slack/commands`
   - Create `/agent-status` pointing to `https://<your-ngrok-url>.ngrok.io/webhooks/slack/commands`
4. **Interactivity**:
   - Enable Interactivity.
   - Set Request URL to `https://<your-ngrok-url>.ngrok.io/webhooks/slack/interactions`
5. **Event Subscriptions**:
   - Enable Events.
   - Set Request URL to `https://<your-ngrok-url>.ngrok.io/webhooks/slack/events`
   - Subscribe to bot events: `app_mention` and `message.channels`.
6. **OAuth & Permissions**:
   - Add scopes: `chat:write`, `commands`, `app_mentions:read`, `channels:history`, `im:history`.
   - Install to Workspace.
7. **Environment Variables**:
   - Copy `Bot User OAuth Token` into `.env` as `SLACK_BOT_TOKEN`.
   - Copy `Signing Secret` (under Basic Information) into `.env` as `SLACK_SIGNING_SECRET`.

## 3. Sample `.agent_policy.yml` Setup

In the root of your target iOS app repository, create `.agent_policy.yml` with the following:

```yaml
version: 1.0
architecture: "MVVM / Composable Architecture"
forbidden_paths:
  - "**/*.entitlements"
  - "**/Provisioning/**"
  - "App/Info.plist" # Only allow human edits to plist
linting:
  enforce_swiftlint: true

# Describe constraints the agent should follow
guidelines: "Prioritize UIKit declarative code using Construkt. Refer to `.agents/skills`."
```
