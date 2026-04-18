# Phase 1: Control Plane Initialization & Mapping

This document provides a highly detailed plan for executing **Phase 1** of the Generalized iOS Agentic Coding Architecture. It outlines how we will establish the fundamental communication and execution infrastructure (the Control Plane) by bridging GitHub and Slack through a custom backend orchestrator.

## Goal Description
Establish the foundational communication layer ("Control Plane") for the iOS Agentic Coding Platform. This involves creating and configuring a GitHub App, a Slack App, and a FastAPI integration backend, and wiring them up to a target sample iOS repository. The goal is to ensure two-way real-time communication: GitHub repository events trigger Slack alerts/approvals, and Slack interactions (slash commands and Block Kit buttons) can trigger backend operations.

---

## Proposed Steps

### 1. Sample iOS Repository configuration
We need a sandbox to test the agent's permissions.
- **Action**: Create or designate a lightweight public sample iOS repository (e.g., `agentic-ios-sandbox`).
- Add a basic Xcode Swift/SwiftUI project to it.
- Create an initial agent policy file `/.agent_policy.yml` in the root containing baseline rules:
  - Allowed architectures.
  - Forbidden paths (e.g., `*.entitlements`, `Provisioning` configurations).
  - Core styling/linting rules.

### 2. GitHub App Setup (GitOps Trigger)
We will transition away from relying on personal access tokens (PATs) and use a dedicated GitHub App to interact with the codebase.
- **Action**: Register a new GitHub App in the GitHub Developer Settings.
- **Permissions needed**:
  - `Contents`: Read & Write (required to read code and create commits).
  - `Issues`: Read & Write (required to read issue details and submit agent thoughts as comments).
  - `Pull Requests`: Read & Write (required to create PRs and respond to code review).
  - `Metadata`: Read-only.
- **Webhooks configuration**: Configure the App to subscribe to `Issues`, `Issue comment`, `Pull request`, and `Push` events. Point the Webhook URL to our FastAPI backend.
- **Secrets**: Generate a Private Key, Webhook Secret, and save the App ID / Client Secret securely.
- **Installation**: Install the GitHub App on the sample repository.

### 3. Slack App Setup (ChatOps Trigger)
We will build the Slack interface for developers to interact with the bot interactively.
- **Action**: Create a new App at `api.slack.com`.
- **Bot Token Scopes**:
  - `chat:write` (to post messages).
  - `commands` (to register slash commands).
  - `app_mentions:read` (to listen for `@agent` pings).
  - `im:history`, `channels:history` (to read thread context for isolated task tracking).
- **Features to Enable**:
  - Interactivity & Shortcuts: Enable this to handle payload submissions when a user clicks a built-in Block Kit button (like "Approve Deployment").
  - Slash Commands: Create commands like `/ios-agent` and `/agent-status`.
  - Event Subscriptions: Subscribe to `app_mention` and `message.channels`.
- **Installation**: Install the App to a designated Slack workspace and invite the bot to a designated channel (e.g., `#agent-ops`).

### 4. FastAPI Backend Orchestrator Stub
This is the central nervous system written in Python that bridges the gap between LangGraph (later), GitHub, and Slack.
- **Stack**: Python 3.10+, `FastAPI`, `Uvicorn`, `PyGithub` (for GitHub REST API), `slack_bolt` (or `slack_sdk`).
- **Core Endpoints**:
  - `POST /webhooks/github`: Parses GitHub events. For example, if a new Issue mapping to the agent is opened, it routes an approval/notification payload to Slack.
  - `POST /webhooks/slack/events`: Handles general Slack Events API (mentions).
  - `POST /webhooks/slack/interactions`: Handles Slack button clicks (e.g., user clicking "Approve PR").
  - `POST /webhooks/slack/commands`: Handles slash commands and replies appropriately.
- **Local Dev Connectivity**: We will define standard local startup scripts to spin up `ngrok` or `localtunnel`. This exposes our local FastAPI port (`8000`) to the public internet so GitHub and Slack can successfully deliver webhooks during active development.

---

## Verification Plan

We will verify Phase 1 is complete when the following "Hello World" flows succeed continuously:

### Flow A (GitHub to Slack)
1. User opens a new Issue in the sample repository and tags the agent.
2. GitHub Webhook fires to the FastAPI backend.
3. The backend parses the payload and successfully posts a formatted Block Kit message to the designated Slack channel: *"New Agent Task created: [Issue Title]"*, including a mock "Acknowledge" button.

### Flow B (Slack to Backend)
1. User clicks the "Acknowledge" button on the Slack message from Flow A.
2. Slack Interactivity webhook fires to the FastAPI backend.
3. The backend successfully parses the button payload, updates the Slack message visually, and logs the human's approval.

### Flow C (Command Invocation)
1. User runs `/agent-status` in Slack.
2. FastAPI intercepts the command and responds directly in the channel with: *"System Online. GitHub App connected."*
