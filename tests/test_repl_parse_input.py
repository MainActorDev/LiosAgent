"""Tests for the parse_input pure function."""

import os
import pytest
from agent.repl.parse_input import parse_input


def test_no_mentions_returns_unchanged(tmp_path):
    text, attachments = parse_input("hello world", str(tmp_path))
    assert text == "hello world"
    assert attachments == []


def test_single_file_mention(tmp_path):
    test_file = tmp_path / "readme.md"
    test_file.write_text("# Hello\nWorld\n")

    text, attachments = parse_input("check @readme.md please", str(tmp_path))

    assert "### Injected Context from @mentions:" in text
    assert "--- readme.md ---" in text
    assert "# Hello" in text
    assert len(attachments) == 1
    assert attachments[0]["path"] == "readme.md"
    assert attachments[0]["lines"] == 2


def test_multiple_file_mentions(tmp_path):
    (tmp_path / "a.py").write_text("line1\nline2\nline3\n")
    (tmp_path / "b.py").write_text("x\n")

    text, attachments = parse_input("compare @a.py and @b.py", str(tmp_path))

    assert len(attachments) == 2
    paths = {a["path"] for a in attachments}
    assert paths == {"a.py", "b.py"}


def test_duplicate_mentions_deduplicated(tmp_path):
    (tmp_path / "file.txt").write_text("content\n")

    text, attachments = parse_input("@file.txt and @file.txt again", str(tmp_path))

    # Should only attach once
    assert len(attachments) == 1


def test_missing_file_still_noted(tmp_path):
    text, attachments = parse_input("look at @nonexistent.py", str(tmp_path))

    assert "nonexistent.py (NOT FOUND)" in text
    assert attachments == []


def test_file_read_error(tmp_path):
    # Create a directory with the same name as the mention (can't read as file)
    (tmp_path / "adir").mkdir()

    text, attachments = parse_input("check @adir", str(tmp_path))

    # adir is not a file, so it should be NOT FOUND
    assert attachments == []
