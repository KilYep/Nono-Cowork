from tools.tools import (run_command, check_command_status,
                        web_search, read_webpage, read_file, edit_file)
from tools.syncthing import sync_status, sync_wait


# Tool registry: function name → actual function
tools_map = {
    "read_webpage": read_webpage,
    "web_search": web_search,
    "run_command": run_command,
    "check_command_status": check_command_status,
    "read_file": read_file,
    "edit_file": edit_file,
    "sync_status": sync_status,
    "sync_wait": sync_wait,
}


# Tool schema definitions (tells the model which tools are available)
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": "Read webpage content and convert it to readable text. Use this to view specific web pages from search results, read documentation, GitHub READMEs, tech blogs, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the webpage to read.",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet using a search engine. Use this when you need to find general (non-academic) information such as tool documentation, tech blogs, error solutions, open-source project info, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keywords.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return. Default is 5.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a bash command on the Linux server. Can be used for: git clone, installing dependencies (pip install), running Python scripts, viewing file contents (cat/ls/find), creating directories, and any other terminal operations. The command output is returned immediately upon completion; if it does not finish within 120 seconds, a PID is returned and you can use check_command_status to view the result later.\n\nOutput management: When the output exceeds 1000 lines or 100KB, it is automatically saved to a temporary file. A summary and the file path are returned; use read_file to view the full content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute. Supports pipes, redirects, etc. Examples: 'ls -la', 'git clone ...', 'pip install -r requirements.txt'.",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory for the command. Defaults to the user's home directory.",
                        "default": "~",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_command_status",
            "description": "Check the status and output of a background command. Use this when run_command returns a PID to monitor progress. You can control how many characters to return and whether to prioritize the head or tail of the output. If the output is very large, it is automatically saved to a file that can be read with read_file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {
                        "type": "integer",
                        "description": "The process PID, returned by run_command when the command did not finish within the timeout.",
                    },
                    "output_chars": {
                        "type": "integer",
                        "description": "Maximum number of characters of output to return. Default is 8000. Use a smaller value to save context tokens.",
                        "default": 8000,
                    },
                    "priority": {
                        "type": "string",
                        "description": "Output priority: 'head' (show the beginning), 'tail' (show the end, default — best for viewing latest progress and errors), 'split' (show both head and tail, half each).",
                        "enum": ["head", "tail", "split"],
                        "default": "tail",
                    },
                },
                "required": ["pid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents with optional line range. Use this to view code, config files, READMEs, etc. Output includes line numbers for easy reference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path (absolute or relative).",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-indexed). If not specified, starts from the beginning.",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (inclusive). If not specified, reads to the end of the file.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file using search-and-replace. Performs an exact match on old_text and replaces it with new_text. Prefer this tool for modifying files instead of rewriting the entire file with run_command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to edit.",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "The original text to replace. Must exactly match the file content, including whitespace and indentation. Use read_file first to view the file, then copy the section you want to modify.",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "The new text to replace the old text with.",
                    },
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sync_status",
            "description": "Check Syncthing synchronization status. Displays all synced folder paths, their sync status, and whether the user's device is online. Call this before operating on synced folders to confirm synchronization is healthy.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sync_wait",
            "description": "Wait for file synchronization to complete. Call this after modifying files in a synced folder to ensure changes have been synced to the user's local machine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_id": {
                        "type": "string",
                        "description": "Synced folder ID, obtainable via sync_status(). Default is 'default'.",
                        "default": "default",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Maximum number of seconds to wait. Default is 30.",
                        "default": 30,
                    },
                },
            },
        },
    },
]
