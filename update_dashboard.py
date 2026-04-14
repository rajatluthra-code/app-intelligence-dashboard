#!/usr/bin/env python3
"""
Inject a new day's data into the App Intelligence Dashboard.

Usage:
    python3 update_dashboard.py --date 2026-04-15 --data '{"date":"2026-04-15", ...}'

Or pipe JSON via stdin:
    echo '{"date":"2026-04-15", ...}' | python3 update_dashboard.py --date 2026-04-15

The script:
1. Reads index.html
2. Finds the DAILY_DATA object
3. Inserts/updates the entry for the given date
4. Writes back index.html
5. Optionally commits and pushes to GitHub
"""

import argparse
import json
import re
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(SCRIPT_DIR, "index.html")
MARKER = "// ^^^ NEW DAILY DATA ENTRIES GET APPENDED ABOVE THIS LINE ^^^"


def read_index():
    with open(INDEX_PATH, "r") as f:
        return f.read()


def write_index(content):
    with open(INDEX_PATH, "w") as f:
        f.write(content)


def inject_data(html, date_str, data_json):
    """Insert or replace a date entry in DAILY_DATA.

    Strategy: find the entry by its date key, then locate its end by counting
    brace depth so we never over-consume into adjacent entries or code.
    """
    # Find the start of this date's entry
    entry_start_pattern = re.compile(r'^  "' + re.escape(date_str) + r'": \{', re.MULTILINE)
    match = entry_start_pattern.search(html)

    if match:
        # Found existing entry — find its end by counting braces
        start = match.start()
        brace_start = match.end() - 1  # position of the opening {
        depth = 1
        pos = brace_start + 1
        while pos < len(html) and depth > 0:
            if html[pos] == '{':
                depth += 1
            elif html[pos] == '}':
                depth -= 1
            pos += 1
        # pos is now right after the closing }
        # Skip optional comma and newline
        if pos < len(html) and html[pos] == ',':
            pos += 1
        if pos < len(html) and html[pos] == '\n':
            pos += 1

        new_entry = f'  "{date_str}": {data_json},\n'
        html = html[:start] + new_entry + html[pos:]
        print(f"  Updated existing entry for {date_str}")
    else:
        # Append before the marker
        indent_data = f'  "{date_str}": {data_json},\n'
        html = html.replace(MARKER, indent_data + MARKER)
        print(f"  Added new entry for {date_str}")

    return html


def git_commit_and_push(date_str):
    """Commit and push changes to GitHub."""
    os.chdir(SCRIPT_DIR)
    try:
        subprocess.run(["git", "add", "index.html"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"Daily update: {date_str} report data"],
            check=True, capture_output=True
        )
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            check=True, capture_output=True, text=True
        )
        print(f"  Pushed to GitHub. Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Git error: {e.stderr.strip() if e.stderr else e}")
        return False


def build_data_template(date_str, date_formatted, raw_data):
    """
    Build a DAILY_DATA entry from raw agent data.
    raw_data should be a dict with the day's metrics.
    If raw_data is already a complete DAILY_DATA entry, return it as-is.
    """
    # If it already has the full structure, just return it
    if "qbo" in raw_data and "grand" in raw_data:
        return raw_data

    # Otherwise build from a simplified input
    # (This is a template — the agent fills in the full structure)
    return raw_data


def main():
    parser = argparse.ArgumentParser(description="Update App Intelligence Dashboard with new daily data")
    parser.add_argument("--date", required=True, help="Date string YYYY-MM-DD")
    parser.add_argument("--data", help="JSON string of the daily data (or pass via stdin)")
    parser.add_argument("--push", action="store_true", default=True, help="Commit and push to GitHub (default: true)")
    parser.add_argument("--no-push", action="store_true", help="Skip git commit/push")
    args = parser.parse_args()

    # Get data from args or stdin
    if args.data:
        data_json = args.data
    elif not sys.stdin.isatty():
        data_json = sys.stdin.read().strip()
    else:
        print("Error: Provide --data JSON or pipe via stdin")
        sys.exit(1)

    # Validate JSON
    try:
        data_obj = json.loads(data_json)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON — {e}")
        sys.exit(1)

    # Pretty-print the JSON for readable diffs
    pretty_json = json.dumps(data_obj, indent=4, ensure_ascii=False)

    print(f"Updating dashboard for {args.date}...")
    html = read_index()
    html = inject_data(html, args.date, pretty_json)
    write_index(html)
    print(f"  index.html updated")

    if not args.no_push:
        print("Committing and pushing...")
        if git_commit_and_push(args.date):
            print(f"Done! Dashboard will be live in ~30s at:")
            print(f"  https://rajatluthra-code.github.io/app-intelligence-dashboard/")
        else:
            print("Warning: Git push failed. Changes saved locally.")
    else:
        print("Skipped git push (--no-push)")

    print("Done!")


if __name__ == "__main__":
    main()
