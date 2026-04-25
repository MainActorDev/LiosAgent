"""File mention autocomplete for the Lios REPL input."""

import os
from prompt_toolkit.completion import Completer, Completion


class FileMentionCompleter(Completer):
    """Triggers on '@', suggests file paths from the working directory."""

    def get_completions(self, document, complete_event):
        word_before_cursor = document.get_word_before_cursor(WORD=True)

        if not word_before_cursor.startswith("@"):
            return

        path_prefix = word_before_cursor[1:]

        # Block traversal outside current directory
        if ".." in path_prefix.split(os.sep):
            return

        dirname = os.path.dirname(path_prefix)
        basename = os.path.basename(path_prefix)

        search_dir = dirname if dirname else "."

        try:
            entries = os.listdir(search_dir)
        except OSError:
            return

        for entry in entries:
            if entry.startswith("."):
                continue

            if entry.startswith(basename):
                full_path = os.path.join(search_dir, entry)
                completion_text = entry
                if os.path.isdir(full_path):
                    completion_text += "/"

                yield Completion(completion_text, start_position=-len(basename))
