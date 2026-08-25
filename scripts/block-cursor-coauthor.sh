#!/bin/bash
# Optional Cursor hook: block git commit commands that add Cursor as co-author.
# To enable, add to .cursor/hooks.json under beforeShellExecution:
#   { "command": "scripts/block-cursor-coauthor.sh", "matcher": "git\\s+commit" }
input=$(cat)
command=$(echo "$input" | jq -r '.command // empty')

if [[ "$command" =~ [Cc]o-[Aa]uthored-[Bb]y:.*[Cc]ursor ]] || \
   [[ "$command" =~ --trailer[[:space:]]+[\"']?Co-authored-by:.*[Cc]ursor ]] || \
   [[ "$command" =~ --trailer=Co-authored-by:.*[Cc]ursor ]]; then
  echo '{
    "permission": "deny",
    "user_message": "This commit would add Cursor as co-author. Commits in this repo must not include Co-authored-by Cursor trailers.",
    "agent_message": "Remove all Co-authored-by Cursor trailers and --trailer flags naming Cursor, then retry git commit."
  }'
  exit 0
fi

echo '{ "permission": "allow" }'
exit 0
