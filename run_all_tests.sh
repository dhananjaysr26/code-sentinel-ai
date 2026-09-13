#!/bin/bash
echo "=== 1. single-js ==="
python evaluate.py --repo /Users/dhananjaysingh/Uncoders/AI_APP/code-sentinel-ai/test-repo/single-js --base HEAD~1 --target HEAD --provider bedrock --runs 1

echo "=== 2. auth-bypass ==="
python evaluate.py --repo /Users/dhananjaysingh/Uncoders/AI_APP/code-sentinel-ai/test-repo/auth-bypass --base HEAD~1 --target HEAD --provider bedrock --runs 1

echo "=== 3. multi-loop ==="
python evaluate.py --repo /Users/dhananjaysingh/Uncoders/AI_APP/code-sentinel-ai/test-repo/multi-loop --base HEAD~1 --target HEAD --provider bedrock --runs 1

echo "=== 4. seed_repo ==="
python evaluate.py --repo /Users/dhananjaysingh/Uncoders/AI_APP/code-sentinel-ai/test-repo/seed_repo --base HEAD~5 --target HEAD --provider bedrock --runs 1
