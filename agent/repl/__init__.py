"""
agent.repl package — Textual TUI for Lios-Agent REPL.

Re-exports public API for backward compatibility with `from agent.repl import X`.
Initially re-exports from the renamed old module; updated to use new modules in Task 12.
"""

from agent.repl_old import FileMentionCompleter, LiosLexer, UniversalREPL

__all__ = ["UniversalREPL", "FileMentionCompleter", "LiosLexer"]
