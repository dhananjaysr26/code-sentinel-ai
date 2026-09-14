#!/usr/bin/env bash
source backend/.venv/bin/activate

echo "Evaluating auth-bypass..."
python evaluate.py --repo $(pwd)/test-repo/auth-bypass --base HEAD~1 --target HEAD --runs 3 > eval_auth_bypass.log 2>&1

echo "Evaluating multi-loop..."
python evaluate.py --repo $(pwd)/test-repo/multi-loop --base HEAD~1 --target HEAD --runs 3 > eval_multi_loop.log 2>&1

echo "Evaluating seed_repo..."
python evaluate.py --repo $(pwd)/test-repo/seed_repo --base HEAD~1 --target HEAD --runs 3 > eval_seed_repo.log 2>&1

echo "Evaluating single-js..."
python evaluate.py --repo $(pwd)/test-repo/single-js --base HEAD~1 --target HEAD --runs 3 > eval_single_js.log 2>&1

echo "Evaluating breakableflask..."
python evaluate.py --repo $(pwd)/test-repo/breakableflask --base b3297f7~1 --target b3297f7 --runs 3 > eval_breakableflask.log 2>&1

echo "All 5 evaluations complete!"
