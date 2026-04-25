"""Design tokens and Textual CSS for the Lios TUI."""

# ── Color Tokens ──────────────────────────────────────────────
BG_DEEP = "#0B1120"
BG_PRIMARY = "#0F172A"
BG_SURFACE = "#1E293B"
BG_ELEVATED = "#334155"

GREEN = "#22C55E"
CYAN = "#06B6D4"
PURPLE = "#A78BFA"
AMBER = "#F59E0B"
RED = "#EF4444"

TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#64748B"

BORDER_SUBTLE = "#1E293B"

# ── Textual Application CSS ──────────────────────────────────
APP_CSS = """
Screen {
    background: """ + BG_PRIMARY + """;
}

/* ── Welcome Banner ─────────────────────────────────────── */
WelcomeBanner {
    padding: 1 2;
    margin: 0 0 1 0;
    border-bottom: solid """ + BORDER_SUBTLE + """;
}

/* ── Chat Log ───────────────────────────────────────────── */
ChatLog {
    height: 1fr;
    overflow-y: auto;
    padding: 0 2;
}

/* ── User Message ───────────────────────────────────────── */
UserMessage {
    padding: 0 0;
    margin: 0 0 1 0;
    height: auto;
}

/* ── Agent Message ──────────────────────────────────────── */
AgentMessage {
    border-left: solid """ + BG_ELEVATED + """;
    padding: 0 0 0 2;
    margin: 0 0 1 0;
    height: auto;
}

.agent-label {
    height: auto;
    margin: 0 0 0 0;
}

AgentMessage Markdown {
    color: """ + TEXT_SECONDARY + """;
    margin: 0;
    padding: 0;
}

/* ── Thinking Indicator ─────────────────────────────────── */
ThinkingIndicator {
    padding: 0 0 0 2;
    height: 1;
    margin: 0 0 1 0;
    color: """ + TEXT_MUTED + """;
}

ThinkingIndicator LoadingIndicator {
    color: """ + PURPLE + """;
    width: 4;
    height: 1;
}

.thinking-label {
    height: 1;
    width: auto;
    padding: 0 0 0 1;
}

/* ── Input Area Container ──────────────────────────────── */
#input-area {
    dock: bottom;
    height: auto;
    max-height: 5;
    background: """ + BG_PRIMARY + """;
    border-top: solid """ + BORDER_SUBTLE + """;
    padding: 1 2 0 2;
}

/* ── Chat Input ─────────────────────────────────────────── */
#input-row {
    height: auto;
    layout: horizontal;
    padding: 0;
    margin: 0;
}

.input-chevron {
    width: 3;
    height: 1;
    color: """ + GREEN + """;
    text-style: bold;
    padding: 0;
    content-align: left middle;
}

ChatInput {
    height: auto;
    max-height: 1;
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
}

ChatInput:focus {
    border: none;
}

/* ── Status Bar ─────────────────────────────────────────── */
StatusBar {
    dock: bottom;
    height: 1;
    background: """ + BG_PRIMARY + """;
    color: """ + TEXT_MUTED + """;
    padding: 0 2;
}
"""
