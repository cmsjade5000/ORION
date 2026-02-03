#!/usr/bin/env python3
"""
Rotate memory: generate daily memory file from session dumps.

This script collects session dump files and compiles them into a daily memory
file located in the `memory/` directory with the naming convention YYYY-MM-DD.md.
"""
import datetime
import glob
import os
import shutil


def main():
    # Determine file paths
    today = datetime.date.today().isoformat()
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    memory_dir = os.path.join(repo_root, 'memory')
    os.makedirs(memory_dir, exist_ok=True)

    # Path for the daily memory file
    daily_file = os.path.join(memory_dir, f"{today}.md")

    # Collect session dumps (assumes session dumps in memory/sessions/)
    session_dir = os.path.join(memory_dir, 'sessions')
    session_files = sorted(glob.glob(os.path.join(session_dir, '*.md')))

    # Write daily memory file
    with open(daily_file, 'w') as out_f:
        out_f.write(f"# Memory for {today}\n\n")
        if session_files:
            out_f.write("## Session Dumps\n\n")
            for path in session_files:
                out_f.write(f"### {os.path.basename(path)}\n\n")
                with open(path) as in_f:
                    out_f.write(in_f.read())
                    out_f.write("\n\n")
        else:
            out_f.write("*(No session dumps found)*\n")

    print(f"Generated daily memory file: {daily_file}")


if __name__ == '__main__':
    main()
