# Security, privacy, and CNDP readiness

## Important limitation

This repository is a development prototype, not a declaration of compliance with
Moroccan Law 09-08 or any healthcare security standard. Processing identifiable
health data in production requires a review by the data controller, qualified
Moroccan privacy counsel, and (where appropriate) the CNDP before deployment.
This checklist is an engineering aid, not legal advice.

## Security controls implemented in this prototype

- Passwords are stored as bcrypt hashes; the user-creation command enforces a
  minimum password length and accepted roles.
- Protected API routes require a signed, expiring JWT and valid active user.
- Request fields, appointment status, dates, risk inputs, pagination, and batch
  size have explicit bounds.
- Dashboard API requests send a Bearer token and have finite timeouts.
- Authenticated API requests are recorded in `audit_logs` with actor, method,
  route template, and timestamp. Request bodies, names, email addresses, and
  other clinical details are intentionally excluded from these logs.
- The optional GenAI assistant is restricted to a loopback Ollama endpoint and
  receives only numeric risk features; the API does not send appointment names,
  contact details, or visit reasons to the model.
- Database credentials are URL-escaped safely, `.env` is excluded from Git, and
  the synthetic-data generator does not erase existing appointments unless
  `--replace` is explicitly supplied.

These controls do not replace TLS, database access control, backups, monitoring,
incident response, or a formal security assessment. Failed login attempts are
not yet rate-limited or audited, and audit-log retention/export controls need
deployment-specific design.

## CNDP / Law 09-08 readiness checklist

Before entering real patient data:

1. **Identify the controller and purpose.** Document who determines why and how
   patient, appointment, and prediction data are processed. Separate care
   operations, analytics, and model development purposes.
2. **Confirm the legal basis and CNDP formalities.** Health information is
   sensitive personal data. Have Moroccan counsel determine the required CNDP
   declaration or prior authorization, and obtain any required approval before
   processing. Do not assume that a user login or patient notice alone is enough.
3. **Provide a clear notice and rights process.** Explain purposes, recipients,
   retention, contact details, and applicable access, rectification, and
   objection rights. Define how requests are verified, answered, and recorded.
4. **Minimize collection and use.** Collect only fields needed for a documented
   purpose. Avoid sending names, contact details, or free-text visit reasons to
   the model if they are not needed. Prefer pseudonymized IDs for model work.
5. **Set retention and deletion rules.** Define schedules for patient records,
   access logs, backups, and model-training extracts. Implement authorized
   deletion/archiving and test that backup expiry follows the policy.
6. **Review hosting and transfers.** Inventory database, backups, monitoring,
   model storage, support access, and subprocessors. If data may be hosted or
   accessed outside Morocco, obtain a legal review of CNDP cross-border transfer
   requirements before enabling it.
7. **Protect access and operations.** Use TLS end-to-end, managed secrets,
   encrypted storage and backups, least-privilege database accounts, MFA for
   privileged users, strong account lifecycle controls, and monitored access.
   Define breach triage and notification responsibilities with counsel.
8. **Assess model use.** Document the model's intended purpose, training data,
   limitations, performance by relevant groups, human review, and a way to
   challenge or correct inaccurate source data. Do not use the risk score as
   the sole basis for denying care or prioritizing access.
9. **Complete a documented risk assessment.** Map data flows and threats,
   review suppliers/contracts, test access controls, and obtain a security and
   privacy sign-off before launch.

Consult the CNDP's official resources at <https://www.cndp.ma/> and have counsel
confirm current forms, procedures, and applicable legal requirements.

## Engineering work still needed before production

- Add login throttling, password reset and revocation/session management, MFA,
  and a documented account provisioning/deprovisioning process.
- Review local model installation, access, resource isolation, model provenance,
  generated-text retention, and output safety before enabling the GenAI feature.
- Add role/permission-specific authorization and automated tests for each role.
- Add an operator-controlled audit retention/export policy, protected log
  access, integrity monitoring, and audit-log failure alerting.
- Require HTTPS and production-grade secret injection; validate database TLS and
  backup encryption in deployment configuration.
- Add automated dependency/security scanning, CI, backup-restore drills, and an
  incident-response runbook.
