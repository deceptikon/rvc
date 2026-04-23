#!/usr/bin/env python3
import os
import sys
import re
import argparse

def find_vault_root(start_path):
    """Finds the nearest 'vault' directory by walking up."""
    curr = os.path.abspath(start_path)
    while curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "vault")):
            return os.path.join(curr, "vault")
        if os.path.basename(curr) == "vault":
            return curr
        curr = os.path.dirname(curr)
    return None

def find_file_by_id(vault_path, item_id):
    """Searches for a file starting with the given ID (e.g., ISSUE-123)."""
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.startswith(item_id):
                return os.path.join(root, file)
    return None

def cmd_get(vault_path, item_id):
    file_path = find_file_by_id(vault_path, item_id)
    if not file_path:
        print(f"Error: Item {item_id} not found in vault.")
        sys.exit(1)

    with open(file_path, 'r') as f:
        print(f.read())
    
    print("\n" + "="*40)
    print(f"💡 RVC NEXT STEP: To ingest all linked specifications and PRDs, run:")
    print(f"   rvc context {item_id}")
    print("="*40)

def cmd_context(vault_path, item_id):
    file_path = find_file_by_id(vault_path, item_id)
    if not file_path:
        print(f"Error: Item {item_id} not found.")
        sys.exit(1)

    with open(file_path, 'r') as f:
        content = f.read()

    # Find all [[links]]
    links = re.findall(r'\[\[(.*?)\]\]', content)
    
    print(f"# RVC Context Assembler: {item_id}\n")
    print(f"Found {len(links)} references. Gathering documentation...\n")

    for link in links:
        # Link might be "EPIC-01" or "PRD-Auth" or "Folder/File"
        link_name = link.split('|')[0] # Handle alias [[Link|Alias]]
        spec_path = None
        
        # Search for the file in the entire vault
        for root, dirs, files in os.walk(vault_path):
            for file in files:
                if file.replace(".md", "") == link_name or file == f"{link_name}.md":
                    spec_path = os.path.join(root, file)
                    break
            if spec_path: break

        if spec_path:
            print(f"--- REFERENCE: [[{link_name}]] ---")
            with open(spec_path, 'r') as f_spec:
                print(f_spec.read())
            print(f"\n--- END OF REFERENCE ---\n")
        else:
            print(f"--- REFERENCE [[{link_name}]] NOT FOUND IN VAULT ---\n")

def main():
    parser = argparse.ArgumentParser(description="RVC CLI - Vault Context Interface for Humans and AI")
    parser.add_argument("command", choices=["get", "context"], help="Action to perform")
    parser.add_argument("id", help="The Issue or Spec ID (e.g., ISSUE-232)")
    parser.add_argument("--path", default=".", help="Path to project or vault")

    args = parser.parse_args()
    
    vault_root = find_vault_root(args.path)
    if not vault_root:
        print("Error: Could not find a 'vault' directory in this path or its parents.")
        sys.exit(1)

    if args.command == "get":
        cmd_get(vault_root, args.id)
    elif args.command == "context":
        cmd_context(vault_root, args.id)

if __name__ == "__main__":
    main()
