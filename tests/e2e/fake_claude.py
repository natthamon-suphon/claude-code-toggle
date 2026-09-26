"""Stands in for the real `claude` in end-to-end tests.

It logs how it was started, then sends statusline JSON to cct the way Claude
Code does. Environment:
  FAKE_LOG               file to append one JSON line per start to
  FAKE_STATUSLINE_ARGV   JSON list: the statusline command to run
  FAKE_EXIT              exit code to return (default 0)
"""

import json
import os
import subprocess
import sys
import time
import uuid

args = sys.argv[1:]
session_id = args[args.index("--resume") + 1] if "--resume" in args else str(uuid.uuid4())
account = os.environ.get("CCT_ACCOUNT")
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as log:
    log.write(
        json.dumps({"args": args, "CCT_ACCOUNT": account, "CLAUDE_CONFIG_DIR": os.environ.get("CLAUDE_CONFIG_DIR")})
    )
    log.write("\n")

pct = {"main": 97, "acc2": 40, "acc3": 5}.get(account, 1)
payload = {
    "session_id": session_id,
    "cwd": os.getcwd(),
    "workspace": {"project_dir": os.getcwd(), "current_dir": os.getcwd()},
    "rate_limits": {
        "five_hour": {"used_percentage": pct, "resets_at": int(time.time()) + 4000},
        "seven_day": {"used_percentage": pct / 3, "resets_at": "2099-01-02T03:04:05Z"},
    },
}
result = subprocess.run(
    json.loads(os.environ["FAKE_STATUSLINE_ARGV"]), input=json.dumps(payload), capture_output=True, text=True
)
print("STATUSLINE>", result.stdout.strip(), result.stderr.strip())
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
