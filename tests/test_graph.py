import pytest
from agent.graph import should_retry, should_retry_story, should_continue_stories, story_selector_node
from agent.state import AgentState

def test_should_retry_aborts_after_max_attempts():
    # Arrange
    state = {"compile_retry_count": 3, "compiler_errors": ["Failed"]}
    
    # Act
    result = should_retry(state)
    
    # Assert
    assert result == "push"

def test_should_retry_loops_on_error():
    # Arrange
    state = {"compile_retry_count": 1, "compiler_errors": ["Failed"]}
    
    # Act
    result = should_retry(state)
    
    # Assert
    assert result == "coder"

def test_should_retry_story_skips_after_max_attempts():
    # Arrange
    state = {"compile_retry_count": 3, "history": ["Validator: build failed"]}
    
    # Act
    result = should_retry_story(state)
    
    # Assert
    assert result == "story_skip"

def test_should_retry_story_commits_on_success():
    # Arrange
    state = {"compile_retry_count": 0, "history": ["Validator: PASSED"]}
    
    # Act
    result = should_retry_story(state)
    
    # Assert
    assert result == "story_commit"

def test_story_selector_node_picks_parallel_stories():
    # Arrange
    stories = [
        {"id": "US-1", "title": "A", "target_files": ["file1.swift"]},
        {"id": "US-2", "title": "B", "target_files": ["file2.swift"]},
        {"id": "US-3", "title": "C", "target_files": ["file1.swift"]} # Conflicts with US-1
    ]
    state = {
        "prd_stories": stories,
        "active_story_ids": [],
        "completed_story_ids": [],
        "skipped_story_ids": []
    }
    
    # Act
    new_state, sends = story_selector_node(state)
    
    # Assert
    assert "US-1" in new_state["active_story_ids"]
    assert "US-2" in new_state["active_story_ids"]
    assert "US-3" not in new_state["active_story_ids"] # Skipped due to file conflict
    assert len(sends) == 2
