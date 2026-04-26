The user wants to know how to install and use Lios-Agent. I can provide the instructions from the README.md.

Installation:
1. Ensure you have Python 3.10+, Xcode (with Command Line Tools), NVM/Node, and NPM/OpenCode CLI installed.
2. Install OpenCode CLI globally: `npm i -g opencode-ai@latest`
3. Copy `.env.example` to `.env` and configure your API keys (e.g., `OPENAI_API_KEY`, `GITHUB_APP_ID`).
4. Set up the Python environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
5. Run the CLI: `./lios --help`

Usage:
1. **Epic Initialization:** Run `./lios epic <epic_name>` to start a new feature vault. You will enter the Universal REPL to provide requirements.
2. **Execute:** Run `./lios execute .lios/epics/<epic_name>` to generate the architecture and pause for review.
3. **Approval:** Approve the blueprint in the terminal to let the agent start coding in the isolated vault.
