"""Pygments lexer for Lios REPL input highlighting."""

from pygments.lexer import RegexLexer
from pygments.token import Token


class LiosLexer(RegexLexer):
    name = "Lios"
    aliases = ["lios"]
    filenames = []

    tokens = {
        "root": [
            (r"^/\w+", Token.Keyword),         # Slash commands
            (r"@[\w./-]+", Token.Name.Class),   # File paths
            (r"[^/@\n]+", Token.Text),          # Standard text
            (r".", Token.Text),                  # Fallback
        ]
    }
