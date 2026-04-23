#!/usr/bin/env python3
import subprocess
import json
import os
import sys
import re

def run_command(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None
    return result.stdout

def sanitize_filename(name):
    return re.sub(r'[\\/*?:\"<>|]', "", name).replace(" ", "-")

def gh_to_md(repo, output_dir):
    print(f"Fetching issues from {repo}...")
    issues_json = run_command(f"gh issue list -R {repo} --limit 100 --state open --json number,title,body,labels,createdAt,author")
    if not issues_json:
        return

    issues = json.loads(issues_json)
    os.makedirs(output_dir, exist_ok=True)

    for issue in issues:
        num = issue['number']
        title = issue['title']
        body = issue['body'] or ""
        labels = [l['name'] for l in issue['labels']]
        author = issue['author']['login']
        created = issue['createdAt'][:10]
        
        filename = f"ISSUE-{num}-{sanitize_filename(title)}.md"
        file_path = os.path.join(output_dir, filename)
        
        # Simple mapping of labels to priority/type
        priority = "Medium"
        if "high" in [l.lower() for l in labels]: priority = "High"
        if "bug" in [l.lower() for l in labels]: issue_type = "bug"
        else: issue_type = "story"

        content = f"""
---
id: ISSUE-{num}
type: {issue_type}
status: To Do
priority: {priority}
assignee: "@{author}"
created: {created}
tags: {labels}
repo: {repo}
---
# {title}

## Description
{body}

## GitHub Link
[Issue #{num}](https://github.com/{repo}/issues/{num})
"""
        with open(file_path, "w") as f:
            f.write(content)
        print(f"Created: {filename}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: ./rvc-sync.py <repo> <output_dir>")
        sys.exit(1)
    gh_to_md(sys.argv[1], sys.argv[2])
