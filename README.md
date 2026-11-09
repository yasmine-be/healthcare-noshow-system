# Healthcare No-Show System

A prototype appointment-management API and Streamlit dashboard with an experimental
no-show risk model. The included/generated data is synthetic; model scores are not
validated for clinical or operational decision-making.

## Requirements

- Python 3.10 or later
- PostgreSQL

## Setup

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set the database settings in `.env`. Use a unique random `SECRET_KEY` of at least
32 characters in real deployments; do not commit `.env` or use the example values.
Alternatively, configure a SQLAlchemy `DATABASE_URL` instead of the `DB_*` values.

Apply the schema before starting the API:

```powershell
alembic upgrade head
```

The initial migration creates missing tables and indexes while preserving
existing tables and data. It does not alter columns in existing tables, so
review and migrate any legacy schema differences explicitly. It intentionally
cannot be downgraded. Back up the database before applying future migrations.

Create a login:

```powershell
python create_user.py
```

Start the API and dashboard in separate terminals:

```powershell
uvicorn main:app --reload
```

```powershell
streamlit run dashboard.py
```

The API is available at `http://127.0.0.1:8000`; OpenAPI docs are at `/docs`.
Set `API_URL` in the environment if the dashboard should use a different API URL.
Review [SECURITY_PRIVACY.md](./SECURITY_PRIVACY.md) before using personal data
and [IMPROVEMENT_ROADMAP.md](./IMPROVEMENT_ROADMAP.md) for prioritized next steps.

## Local GenAI staff assistant

Install Ollama locally, download a supported local model (default: `qwen2.5:3b`),
and keep the Ollama service bound to loopback:

```powershell
ollama pull qwen2.5:3b
ollama serve
```

Set `OLLAMA_MODEL` and, if needed, `OLLAMA_BASE_URL` in `.env`. The API refuses
non-loopback GenAI endpoints. In the dashboard, select an appointment and
explicitly request a suggestion. The assistant receives only numeric features
and the model risk band, and returns workflow suggestions for human review; it
does not receive patient identity or visit reason and must not be used for
clinical decisions. If Ollama is unavailable, the endpoint returns a clear
service error and ordinary dashboard functions remain available.

## Model workflow

The repository's `model.pkl` is a pre-trained artifact. Retraining reads real
appointments from PostgreSQL, computes only strictly earlier-date patient history,
uses a chronological holdout, and prints precision, recall, F1, ROC-AUC, PR-AUC,
and Brier score:

```powershell
python train_model.py
```

Do not treat evaluation on the synthetic sample as evidence of real-world
performance. The synthetic generator is deterministic and inserts data without
deleting existing appointments by default:

```powershell
python generate_data.py --count 250 --seed 42
```

Use `--replace` only when intentionally replacing all appointment rows; that
operation is destructive.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The GitHub Actions workflow runs tests, Python compilation, and migration
discovery on pushes and pull requests.
