#!/usr/bin/env python3
"""
Heartbeat summary script to report current task, git status, gateway health, schedule entries,
and send a TTS voice note via Telegram.
"""
import subprocess
from pathlib import Path


def read_current_task():
    """
    Read the current task from memory/WORKING.md under "## Current Task" header.
    """
    base = Path(__file__).parent.parent
    path = base / 'memory' / 'WORKING.md'
    try:
        lines = path.read_text().splitlines()
    except Exception as e:
        return f"Error reading current task: {e}"
    task = None
    for i, line in enumerate(lines):
        if line.strip() == '## Current Task':
            if i + 1 < len(lines):
                task = lines[i + 1].strip()
            break
    return task or "No current task found."


def run_command(cmd):
    """
    Run a command and return its output (stdout+stderr) as a string.
    """
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return result.stdout.strip()
    except Exception as e:
        return f"Error running {' '.join(cmd)}: {e}"


def read_schedule_entries(n=5):
    """
    Read the last n schedule entries (lines starting with '-') from HEARTBEAT.md.
    """
    base = Path(__file__).parent.parent
    path = base / 'HEARTBEAT.md'
    if not path.exists():
        return "No HEARTBEAT.md found."
    try:
        entries = [l.strip() for l in path.read_text().splitlines() if l.strip().startswith('-')]
        if not entries:
            return "No schedule entries found."
        return '\n'.join(entries[-n:])
    except Exception as e:
        return f"Error reading schedule entries: {e}"


def main():
    current_task = read_current_task()
    git_status = run_command(['git', 'status', '--short'])
    gateway_status = run_command(['openclaw', 'gateway', 'status'])
    schedule = read_schedule_entries()

    # Compile summary text
    parts = [
        "Heartbeat Summary:",
        f"Current Task: {current_task}",
        "",
        "Git Status:",
        git_status or "Clean working directory.",
        "",
        "Gateway Status:",
        gateway_status,
        "",
        "Recent Schedule Entries:",
        schedule
    ]
    summary_text = "\n".join(parts)
    print(summary_text)

    # Generate TTS voice note
    tts_output = run_command(['openclaw', 'tts', '--text', summary_text])
    # Extract media path (strip prefix if present)
    media = tts_output.replace("MEDIA: ", "").strip()
    # Send voice note to Telegram
    send_output = run_command(['openclaw', 'message', 'send', '--to', '8471523294', '--media', media])
    print(f"Sent voice note: {media}")


if __name__ == '__main__':
    main()
