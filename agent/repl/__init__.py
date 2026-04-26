"""
agent.repl package — Textual TUI for Lios-Agent REPL.

Re-exports public API for backward compatibility with `from agent.repl import X`.
"""

from agent.repl.completer import FileMentionCompleter
from agent.repl.lexer import LiosLexer
from agent.repl.legacy import UniversalREPL

__all__ = ["UniversalREPL", "FileMentionCompleter", "LiosLexer"]
