import os
import pytest
from unittest.mock import patch, MagicMock
from prompt_toolkit.document import Document
from prompt_toolkit.completion import Completion
from agent.repl import FileMentionCompleter

@pytest.fixture
def mock_fs(tmp_path):
    # Create a mock file system structure
    (tmp_path / "visible.txt").touch()
    (tmp_path / ".hidden.txt").touch()
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "visible_in_subdir.txt").touch()
    return tmp_path

def test_completer_triggers_on_at():
    completer = FileMentionCompleter()
    document = Document("Hello @")
    
    # We mock os.listdir to return our files instead of actual fs
    with patch('os.listdir', return_value=['visible.txt', '.hidden.txt', 'subdir']):
        with patch('os.path.isdir', side_effect=lambda p: p.endswith('subdir')):
            completions = list(completer.get_completions(document, MagicMock()))
    
    # Should only return visible items
    texts = [c.text for c in completions]
    assert "visible.txt" in texts
    assert "subdir/" in texts
    assert ".hidden.txt" not in texts
    
    # The start_position should replace everything after @
    assert all(c.start_position == 0 for c in completions)

def test_completer_filters_by_prefix():
    completer = FileMentionCompleter()
    document = Document("Read @vis")
    
    with patch('os.listdir', return_value=['visible.txt', 'other.txt']):
        with patch('os.path.isdir', return_value=False):
            completions = list(completer.get_completions(document, MagicMock()))
    
    texts = [c.text for c in completions]
    assert "visible.txt" in texts
    assert "other.txt" not in texts
    assert all(c.start_position == -3 for c in completions) # replacing "vis"

def test_completer_navigates_subdirs(mock_fs, monkeypatch):
    # Change working directory to our mock filesystem
    monkeypatch.chdir(mock_fs)
    
    completer = FileMentionCompleter()
    document = Document("Check @subdir/")
    
    completions = list(completer.get_completions(document, MagicMock()))
    texts = [c.text for c in completions]
    assert "visible_in_subdir.txt" in texts
    assert all(c.start_position == 0 for c in completions)

def test_completer_blocks_parent_traversal():
    completer = FileMentionCompleter()
    document = Document("Look @../")
    
    completions = list(completer.get_completions(document, MagicMock()))
    assert len(completions) == 0

def test_completer_ignores_non_at_text():
    completer = FileMentionCompleter()
    document = Document("Hello world")
    
    completions = list(completer.get_completions(document, MagicMock()))
    assert len(completions) == 0