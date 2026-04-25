"""Pure function to parse @file mentions from user input."""

import os
import re


def parse_input(
    user_input: str, workspace_root: str = "."
) -> tuple[str, list[dict]]:
    """Parse user input for @file mentions.

    Returns:
        A tuple of (processed_text, attachments).
        - processed_text: the original input with file contents appended.
        - attachments: list of {"path": str, "lines": int} for each
          successfully read file.
    """
    pattern = r"@([a-zA-Z0-9_./-]+)"
    matches = re.findall(pattern, user_input)

    if not matches:
        return user_input, []

    compiled_input = user_input + "\n\n### Injected Context from @mentions:\n"
    attachments: list[dict] = []
    seen: set[str] = set()

    for filepath in matches:
        if filepath in seen:
            continue
        seen.add(filepath)

        full_path = os.path.join(workspace_root, filepath)
        if os.path.isfile(full_path):
            try:
                with open(full_path, "r") as f:
                    content = f.read()
                line_count = len(content.splitlines())
                compiled_input += f"\n--- {filepath} ---\n```\n{content}\n```\n"
                attachments.append({"path": filepath, "lines": line_count})
            except Exception:
                compiled_input += f"\n--- {filepath} (ERROR) ---\nCould not read file.\n"
        else:
            compiled_input += f"\n--- {filepath} (NOT FOUND) ---\n"

    return compiled_input, attachments
