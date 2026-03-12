"""
File operation tools — read and edit files.
"""

import os


def read_file(path: str, start_line: int = None, end_line: int = None) -> str:
    """Read file contents with optional line range.

    Args:
        path: File path (absolute or relative)
        start_line: Starting line number (1-indexed), omit to start from beginning
        end_line: Ending line number (inclusive), omit to read to end
    """
    if not os.path.exists(path):
        return f"❌ File not found: {path}"
    if os.path.isdir(path):
        return f"❌ This is a directory, not a file: {path}"

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total = len(lines)
        s = (start_line - 1) if start_line else 0
        e = end_line if end_line else total
        s = max(0, min(s, total))
        e = max(s, min(e, total))

        selected = lines[s:e]

        # Output with line numbers
        numbered = []
        for i, line in enumerate(selected, start=s + 1):
            numbered.append(f"{i:4d} | {line.rstrip()}")

        header = f"📄 {path} ({total} lines total, showing {s+1}-{e})\n"
        return header + "\n".join(numbered)

    except Exception as ex:
        return f"❌ Failed to read file: {str(ex)}"


def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Edit a file using search and replace. Exact match on old_text, replaced with new_text.

    Args:
        path: File path
        old_text: Original text to replace (must exactly match file content, including indentation and newlines)
        new_text: New text to replace with
    """
    if not os.path.exists(path):
        return f"❌ File not found: {path}"

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        count = content.count(old_text)

        if count == 0:
            # Show file snippet to help LLM locate the issue
            lines = content.split("\n")
            preview = "\n".join(lines[:30]) if len(lines) > 30 else content
            return (
                f"❌ No match found. Please verify old_text exactly matches the file content (including whitespace and indentation).\n\n"
                f"First 30 lines:\n{preview}"
            )

        if count > 1:
            # Show all match positions
            positions = []
            start = 0
            for i in range(count):
                pos = content.index(old_text, start)
                line_num = content[:pos].count("\n") + 1
                positions.append(f"  Line {line_num}")
                start = pos + 1
            return (
                f"❌ Found {count} matches, cannot determine which one to replace.\n"
                f"Match positions:\n" + "\n".join(positions) + "\n\n"
                f"Include more surrounding context in old_text to uniquely identify the target."
            )

        # Unique match, perform replacement
        new_content = content.replace(old_text, new_text, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        old_lines = len(old_text.splitlines())
        new_lines = len(new_text.splitlines())
        return f"✅ Replaced ({old_lines} lines → {new_lines} lines)"

    except Exception as ex:
        return f"❌ Edit failed: {str(ex)}"
