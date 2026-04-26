"""
Ralph Integration Module
Provides PRD decomposition and story management for Lios-Agent.
Based on the Ralph pattern: https://github.com/snarktank/ralph
"""

import json
import re
from typing import List, Dict
from pydantic import BaseModel, Field
from agent.llm_factory import get_llm


class UserStory(BaseModel):
    """A single atomic user story in Ralph prd.json format."""
    id: str = Field(description="Sequential ID like US-001")
    title: str = Field(description="Short descriptive name")
    description: str = Field(description="As a [user], I want [X] so that [Y]")
    target_files: List[str] = Field(description="Exact file paths this story will modify or create")
    acceptance_criteria: List[str] = Field(description="Verifiable checklist")
    priority: int = Field(description="Execution order (1 = first)")
    passes: bool = Field(default=False)
    notes: str = Field(default="")


class PRDDocument(BaseModel):
    """Ralph-compatible PRD document."""
    project: str
    branch_name: str
    description: str
    user_stories: List[UserStory]


def decompose_blueprint_to_stories(
    blueprint: dict, 
    instructions: str, 
    mcp_context: str = "",
    progress_log: str = ""
) -> List[dict]:
    """
    Takes an approved FeatureBlueprint and decomposes it into
    atomic, dependency-ordered user stories.
    
    Returns a list of story dicts in prd.json format.
    """
    llm = get_llm(role="planning")
    
    schema = """
You MUST respond with ONLY a valid JSON array (no markdown, no explanation) where each element matches:
{
  "id": "US-001",
  "title": "Short title",
  "description": "As a [user], I want [X] so that [Y]",
  "target_files": ["Exact/Path/To/File.swift", "Another/Path.swift"],
  "acceptance_criteria": ["Criterion 1", "Criterion 2", "xcodebuild compiles"],
  "priority": 1,
  "passes": false,
  "notes": ""
}
"""
    
    prompt = f"""You are breaking down an iOS feature into atomic user stories for autonomous implementation.

FEATURE REQUEST:
{instructions}

ARCHITECTURAL BLUEPRINT (approved by human):
{json.dumps(blueprint, indent=2)}

PROJECT CONTEXT:
{mcp_context[:2000] if mcp_context else 'No additional context.'}

PREVIOUS LEARNINGS:
{progress_log[:1500] if progress_log else 'No prior learnings.'}

RULES:
1. Each story MUST be completable in ONE focused coding session (one OpenCode invocation)
2. Order stories by dependency: schema/model changes → service/repository logic → UI/View changes → integration/tests
3. Every story MUST include "xcodebuild compiles" as an acceptance criterion
4. Stories with UI changes MUST include "Simulator screenshot validates" as a criterion  
5. Do NOT create a story that depends on a later story
6. Right-sized: "Add a new ViewModel" is good. "Build the entire feature" is too big — split it.
7. Include 2-6 stories. If the feature is trivial, 1-2 stories is fine.
8. The "notes" field should contain hints about which specific files from the blueprint this story touches.

{schema}
"""
    
    response = llm.invoke(prompt)
    raw_text = response.content.strip()
    
    # Parse JSON, handling markdown fences
    json_str = raw_text
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw_text, re.DOTALL)
    if fence_match:
        json_str = fence_match.group(1).strip()
    
    try:
        stories = json.loads(json_str)
        if not isinstance(stories, list):
            stories = [stories]
        # Validate each story
        validated = [UserStory(**s).model_dump() for s in stories] # model_dump() for pydantic v2
        # Ensure sorted by priority
        validated.sort(key=lambda s: s.get("priority", 999))
        return validated
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️ PRD decomposition JSON parse failed: {e}")
        # Fallback: single story wrapping the entire blueprint
        return [{
            "id": "US-001",
            "title": blueprint.get("feature_name", "Feature Implementation"),
            "description": instructions[:200],
            "target_files": [],
            "acceptance_criteria": ["xcodebuild compiles", "All blueprint files created/modified"],
            "priority": 1,
            "passes": False,
            "notes": f"Fallback: full blueprint. Parse error: {str(e)[:100]}"
        }]


def format_stories_for_github(stories: list, feature_name: str) -> str:
    """Format the decomposed stories as a GitHub comment for human review."""
    md = f"### 📋 PRD Decomposition: {feature_name}\n\n"
    md += "The approved blueprint has been broken into the following atomic user stories:\n\n"
    
    for s in stories:
        status = "✅" if s.get("passes") else "⬜"
        md += f"#### {status} {s['id']}: {s['title']} (Priority: {s['priority']})\n"
        md += f"> {s['description']}\n\n"
        md += "**Acceptance Criteria:**\n"
        for c in s.get("acceptance_criteria", []):
            md += f"- [ ] {c}\n"
        if s.get("notes"):
            md += f"\n*Notes: {s['notes']}*\n"
        md += "\n---\n\n"
    
    md += f"**Total Stories:** {len(stories)} | **Execution Order:** Priority 1 → {len(stories)}\n\n"
    md += "_Stories will execute sequentially. Each story gets its own OpenCode invocation and git commit._"
    
    return md


def get_current_story(stories: list) -> dict | None:
    """Get the highest-priority story that hasn't passed yet."""
    pending = [s for s in stories if not s.get("passes", False)]
    if not pending:
        return None
    return min(pending, key=lambda s: s.get("priority", 999))


def mark_story_passed(stories: list, story_id: str) -> list:
    """Mark a story as passed and return the updated list."""
    for s in stories:
        if s["id"] == story_id:
            s["passes"] = True
            break
    return stories
