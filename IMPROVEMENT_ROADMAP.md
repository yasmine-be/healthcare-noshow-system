# Improvement roadmap

Prioritize these steps before treating the project as a production service.

## P0 — Release blockers

- Fix and verify authentication end to end; maintain least-privilege roles.
- Complete CNDP/Law 09-08 review, establish the controller, processing purposes,
  required formalities, patient notice/rights workflow, retention, and transfer
  review before using real health data.
- Deploy only behind HTTPS; store secrets in a managed secret store and enforce
  encrypted database connections/backups.
- Add login throttling, MFA for privileged users, account lifecycle controls,
  audit-log retention and alerting, and tested backup restoration.
- Do not use the current synthetic-data-trained model for clinical or
  operational decisions.

## P1 — Reliability and performance

- **Implemented:** move dashboard date filtering, statistics aggregation,
  bounded patient lookup, and patient history pagination into database-side
  API queries; batch predictions rather than issuing one request per row.
- **Implemented:** add the `(date_rdv, id)` composite index used by the
  appointment date/order query.
- Measure query plans against production-like synthetic data before adding more
  indexes; avoid index additions that increase write and storage costs without
  measured benefit.
- Add connection-pool sizing, health/readiness endpoints, structured error
  handling, monitoring, and request tracing.
- Add CI for formatting, static checks, migrations, tests, and dependency
  vulnerability alerts.
- Separate dev/test/prod configuration and database credentials; create a
  repeatable deployment process and rollback/backup plan.

## P2 — Data and machine-learning quality

- Build a versioned, reproducible training pipeline with data validation,
  temporal/group-aware evaluation, model metadata, and artifact provenance.
- Measure precision/recall, PR-AUC, calibration, subgroup performance, and
  operational impact against a baseline; track drift and define retraining
  criteria.
- Document label definitions, cancellations, duplicate appointments, missing
  history, and how same-day appointments are treated.
- Keep inference and training features shared, add contract tests, and monitor
  prediction distributions after release.
- Add human review and a process for correcting source data; never treat model
  scores as a diagnosis or automatic denial of care.

## P3 — Product and maintainability

- Add delete/archive workflows with authorization, confirmation, and audit trail.
- Add search by stable patient ID, date/doctor filters, localization, and
  accessible keyboard/screen-reader behavior.
- Add API versioning, OpenAPI examples, structured logging without sensitive
  payloads, and user-facing error states.
- Split API, dashboard, model, and database modules into a conventional package
  structure as the codebase grows.
- Add integration and load tests using synthetic, non-identifying data.
