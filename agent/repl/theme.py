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

# ── Textual Application CSS ──────────────────────────────────
APP_CSS = """
Screen {
    background: """ + BG_PRIMARY + """;
}

/* ── Welcome Banner ─────────────────────────────────────── */
WelcomeBanner {
    padding: 1 2;
    margin-bottom: 1;
}

/* ── Chat Log ───────────────────────────────────────────── */
ChatLog {
    height: 1fr;
    overflow-y: auto;
    padding: 0 1;
}

/* ── User Message ───────────────────────────────────────── */
UserMessage {
    padding: 0 2;
    margin: 0 0;
}

/* ── Agent Message ──────────────────────────────────────── */
AgentMessage {
    border-left: solid """ + BG_ELEVATED + """;
    padding: 0 0 0 2;
    margin: 1 0;
}

AgentMessage Markdown {
    color: """ + TEXT_SECONDARY + """;
}

/* ── Thinking Indicator ─────────────────────────────────── */
ThinkingIndicator {
    padding: 0 0 0 2;
    height: auto;
    color: """ + TEXT_MUTED + """;
}

ThinkingIndicator LoadingIndicator {
    color: """ + PURPLE + """;
    width: 4;
    height: 1;
}

/* ── Chat Input ─────────────────────────────────────────── */
ChatInput {
    dock: bottom;
    height: auto;
    max-height: 3;
    background: """ + BG_DEEP + """;
    padding: 0 1;
    margin: 0;
}

ChatInput:focus {
    border: solid """ + GREEN + """;
}

/* ── Status Bar ─────────────────────────────────────────── */
StatusBar {
    dock: bottom;
    height: 1;
    background: """ + BG_DEEP + """;
    color: """ + TEXT_MUTED + """;
    padding: 0 2;
}
"""
