#!/usr/bin/env python3
import argparse
import sys
import re
from pathlib import Path

CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"

def add_entry(entry_type: str, message: str):
    if not CHANGELOG_PATH.exists():
        print(f"Error: {CHANGELOG_PATH} not found.")
        sys.exit(1)

    with open(CHANGELOG_PATH, 'r') as f:
        content = f.read()

    # Find the [Unreleased] section
    unreleased_match = re.search(r"##\s*\[Unreleased\]", content)
    if not unreleased_match:
        print("Error: Could not find ## [Unreleased] section in CHANGELOG.md")
        sys.exit(1)

    unreleased_pos = unreleased_match.end()

    # Find the next version header to bound the Unreleased section
    next_version_match = re.search(r"##\s*\[\d+\.\d+\.\d+\]", content[unreleased_pos:])
    
    if next_version_match:
        unreleased_content = content[unreleased_pos:unreleased_pos + next_version_match.start()]
    else:
        unreleased_content = content[unreleased_pos:]

    # Check if the type section exists (e.g., ### Added)
    type_header = f"### {entry_type}"
    type_match = re.search(rf"###\s*{entry_type}", unreleased_content)

    new_entry = f"- {message}\n"

    if type_match:
        # Type section exists, insert after it
        pos = unreleased_pos + type_match.end() + 1 # +1 for newline
        # Find position to insert (after existing items under header)
        lines = content[pos:].split('\n')
        insert_index = 0
        for i, line in enumerate(lines):
            if line.strip() == "" or line.startswith("##") or line.startswith("###"):
                break
            if line.startswith("-"):
                insert_index = i + 1
        
        # Reconstruct content
        before_insert = content[:pos + sum(len(l) + 1 for l in lines[:insert_index])]
        after_insert = content[pos + sum(len(l) + 1 for l in lines[:insert_index]):]
        updated_content = before_insert + new_entry + after_insert

    else:
        # Type section doesn't exist, create it under ## [Unreleased]
        # We insert at the very beginning of the Unreleased section
        insert_pos = unreleased_pos + 1 # after header and newline
        insert_content = f"\n{type_header}\n{new_entry}"
        updated_content = content[:insert_pos] + insert_content + content[insert_pos:]

    with open(CHANGELOG_PATH, 'w') as f:
        f.write(updated_content)

    print(f"Added '{message}' to {entry_type} in CHANGELOG.md")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add an entry to CHANGELOG.md under [Unreleased]")
    parser.add_argument("--type", choices=["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"], required=True, help="Type of change")
    parser.add_argument("--message", required=True, help="Change description")

    args = parser.parse_args()
    add_entry(args.type, args.message)
