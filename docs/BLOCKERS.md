# SAP-CUA Blockers

## Current Blockers

| # | Blocker | Impact | Resolution |
|---|---------|--------|------------|
| B-001 | SAP sandbox credentials | Cannot run live integration tests | User provides credentials |
| B-002 | Git init permission denied in project folder | Cannot init/push repo | User must run: `cd \"/Users/it-stock/Desktop/AI agentic one/SAP_Computer_USE\" && rm -rf .git && git init && git add -A && git commit -m \"Initial scaffold\"` then create GitHub repo and push |
| B-003 | GPU access for heavy training | Cannot run LoRA/RL | Use cloud GPU provider (RunPod, Vast, etc.) |

## Why B-002 exists
The `.git/hooks/` directory has `@` extended attribute with read-only permissions.
Claude Code auto mode blocks writing to it. macOS filesystem ACL prevents git init
from copying hook templates. User must run the commands in Terminal.app directly.

## Resolved Blockers

| # | Blocker | Resolution |
|---|---------|------------|
| - | Git permissions in project folder | Documented as B-002, user must resolve manually |
| - | No SAP access | Mock environment built |
| - | Python 3.9 compatibility | Fixed |
| - | Duplicate history append in MockModel | Fixed |
| - | Duplicate history append in OpenCUAAdapter | Fixed |
| - | Security pattern ordering | Fixed |
| - | Template variable passing | Fixed |
| - | Missing observe() in mock env | Fixed |
| - | Missing execute() in router | Fixed |
| - | Missing agent_loop.py | Fixed |

## Escalation Path

When a blocker is encountered:
1. Record it here
2. Continue with all non-blocked work
3. Document the exact input needed to unblock
4. Do not wait for resolution before continuing
