#!/bin/bash
set -e
git status
ADDITIONAL_COMMENT="$1"

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

git pull
git push
