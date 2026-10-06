# SAP-CUA Security Policy

## Secret Management

- **NO real production credentials** in datasets
- Automatic redaction of passwords, tokens, keys, certificates
- Runtime secrets stored only in: env secret manager, OS keychain, Vault, cloud secret manager
- **Never commit secrets** to git
- Automated secret scanning in CI

## Destructive Action Policies

| Risk Level | Sandbox | Production |
|-----------|---------|------------|
| LOW | Allowed | Allowed |
| MEDIUM | Allowed | Logged |
| HIGH | Allowed | **Requires approval** |
| CRITICAL | Requires approval | **Requires approval** |

##  Defense

Treat external content as **DATA, not **:
- MPL error text
- API responses
- Payload contents
- Package descriptions
- Web pages
- Error messages

Build defenses so malicious content cannot:
- Leak secrets
- Change safety policy
- Bypass authorization

## RBAC

- Role-based access control on all SAP operations
- Least-privilege principle
- Audit log for every action

## MFA / SSO / CAPTCHA

Never automate bypassing:
- MFA
- Hardware security keys
- Authorization boundaries
- CAPTCHA
- SSO security controls

## Audit Logging

Every autonomous action logs:
- Timestamp
- Task
- Model/checkpoint
- Observation hash
- Semantic action
- Executor
- Arguments
- SAP object affected
- Result
- Verifier result
- Risk level
- Approval status

Logs support replay. Never log secret values.
