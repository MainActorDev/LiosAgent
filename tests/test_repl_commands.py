"""Tests for command routing."""

import pytest
from unittest.mock import MagicMock, patch
from agent.repl.commands import route_command, is_command


def test_is_command_true():
    assert is_command("/help") is True
    assert is_command("/exit") is True
    assert is_command("/epic myapp") is True


def test_is_command_false():
    assert is_command("hello") is False
    assert is_command("") is False
    assert is_command("@file.py") is False


@patch("agent.repl.commands._post_system_message")
def test_route_help(mock_post):
    app = MagicMock()
    result = route_command("/help", app)
    assert result == "handled"
    mock_post.assert_called_once()


def test_route_exit():
    app = MagicMock()
    result = route_command("/exit", app)
    app.exit.assert_called_once()
    assert result == "handled"


def test_route_quit():
    app = MagicMock()
    result = route_command("/quit", app)
    app.exit.assert_called_once()
    assert result == "handled"


def test_route_unknown():
    app = MagicMock()
    result = route_command("/foobar", app)
    assert result == "unknown"


@patch("agent.repl.commands._handle_subflow")
def test_route_epic_with_args(mock_subflow):
    app = MagicMock()
    result = route_command("/epic myapp", app)
    assert result == "handled"
    mock_subflow.assert_called_once_with(app, "epic", ["myapp"])


@patch("agent.repl.commands._post_system_message")
def test_route_epic_no_args(mock_post):
    app = MagicMock()
    result = route_command("/epic", app)
    assert result == "error"
