import os
import sys

# Ensure agent package is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pygments.token import Token
from agent.repl import LiosLexer

def test_lios_lexer():
    lexer = LiosLexer()
    
    # Test slash command
    tokens = list(lexer.get_tokens_unprocessed("/help\n"))
    assert len(tokens) == 2
    assert tokens[0][1] == Token.Keyword
    assert tokens[0][2] == "/help"

    # Test file path
    tokens = list(lexer.get_tokens_unprocessed("@src/main.py\n"))
    assert len(tokens) == 2
    assert tokens[0][1] == Token.Name.Class
    assert tokens[0][2] == "@src/main.py"
    
    # Test standard text
    tokens = list(lexer.get_tokens_unprocessed("hello world\n"))
    assert len(tokens) == 2
    assert tokens[0][1] == Token.Text
    assert tokens[0][2] == "hello world"
