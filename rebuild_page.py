#!/usr/bin/env python3
"""
Rebuilds the pokemon-model.astro page from latest results
and pushes to GitHub so Vercel redeploys automatically.
"""
import subprocess
import json
from datetime import datetime

print(f"[{datetime.now().isoformat()}] Rebuilding pokemon model page...")

# Run the model
result = subprocess.run(
    ['python3', '/opt/orchid/apps/pokemon-model/model_v3.py'],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"Model failed: {result.stderr}")
    exit(1)

print("Model run complete. Rebuilding page...")

# Re-run page build (import model_v2 logic inline)
subprocess.run(['python3', '-c', '''
import json, sys
sys.path.insert(0, "/opt/orchid/apps/pokemon-model")
# Page rebuild happens in the model cron — just push
'''], capture_output=True)

# Git push from matterunknown repo
push = subprocess.run(
    ['git', '-C', '/opt/orchid/apps/matterunknown', 'add', 'src/pages/projects/pokemon-model.astro'],
    capture_output=True, text=True
)
commit = subprocess.run(
    ['git', '-C', '/opt/orchid/apps/matterunknown', 'commit', '-m',
     f'chore: refresh pokemon model data {datetime.now().strftime("%Y-%m-%d")}'],
    capture_output=True, text=True
)
push_result = subprocess.run(
    ['git', '-C', '/opt/orchid/apps/matterunknown', 'push', 'origin', 'main'],
    capture_output=True, text=True
)
print(f"Git push: {push_result.stdout or push_result.stderr}")
print("Done.")
