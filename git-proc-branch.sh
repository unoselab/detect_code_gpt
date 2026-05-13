#!/bin/bash
set -e

git status

ADDITIONAL_COMMENT="${1:-}"
CURRENT_BRANCH=$(git branch --show-current)

if [ -z "$CURRENT_BRANCH" ]; then
    echo "Error: could not determine current branch."
    exit 1
fi

echo "Current branch: $CURRENT_BRANCH"

git add .

if ! git diff --cached --quiet; then
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
    if [ -n "$ADDITIONAL_COMMENT" ]; then
        git commit -m "$TIMESTAMP: $ADDITIONAL_COMMENT"
    else
        git commit -m "$TIMESTAMP" -m "Updated"
    fi
else
    echo "Nothing to commit."
fi

git pull --rebase origin "$CURRENT_BRANCH"
git push -u origin "$CURRENT_BRANCH"