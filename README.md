# HRX Backend

FastAPI backend for HRX recruiting and organization workflows.

## Python runtime

Development and production are pinned to Python 3.13.14 through
`.python-version`. Create the virtual environment with that interpreter before
installing dependencies:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## AI agent

The AI agent is available only to authenticated `org_admin` and `hr_manager`
users. Conversations are private to their creator and have an authoritative
`read_mode` or `action_mode`.

Action mode never writes directly from a model function call. The model can only
create one expiring proposal. The proposing user must then call the confirmation
endpoint with an `Idempotency-Key`; the backend rechecks the role, organization,
conversation mode, expiry, and target version before invoking the existing
service.

The agent uses:

- typed service tools for counts, filters, reports, and mutations;
- existing persisted candidate rankings for top-applicant answers;
- Xkiro's OpenAI-compatible chat API with Mistral Large for agent responses,
  resume parsing, and candidate ranking;
- Gemini embeddings and pgvector for organization-scoped semantic retrieval;
- a PostgreSQL outbox and separate worker for durable re-indexing.

### Configuration

Generation uses Xkiro. `GEMINI_API_KEY` is still required only by semantic
indexing because the existing database vectors were built with Gemini's
768-dimensional embedding model.

```dotenv
XKIRO_API_KEY=your-xkiro-api-key
XKIRO_BASE_URL=https://api.xkiro.com/v1
XKIRO_MODEL=mistralai/mistral-large-2512
GEMINI_API_KEY=your-gemini-api-key
GEMINI_EMBEDDING_MODEL=gemini-embedding-2
GEMINI_EMBEDDING_DIMENSIONS=768
AI_ACTION_PROPOSAL_TTL_SECONDS=600
AI_AGENT_MAX_TOOL_ROUNDS=8
AI_INDEX_WORKER_POLL_SECONDS=2
AI_INDEX_WORKER_MAX_ATTEMPTS=5
```

The Xkiro base URL and model above are the defaults and only need to be set when
overriding them. The embedding dimension is part of the database schema.
Changing the embedding provider or dimension requires a new migration and
complete re-index.

### Database and worker

Install dependencies and apply migrations:

```bash
python -m pip install -r requirements.txt
alembic upgrade head
```

The migration enables the PostgreSQL `vector` extension, creates the HNSW index,
and enqueues a backfill for existing jobs and applications.

Run the durable indexing consumer as a separate process:

```bash
python -m scripts.run_ai_index_worker
```

### API flow

1. `POST /api/ai/conversations`
2. `POST /api/ai/conversations/{id}/turns` with `message` and `expected_mode`
3. Consume the SSE events (`text_delta`, `result_block`, `action_proposal`,
   `error`, and `done`).
4. For a reviewed action proposal, call
   `POST /api/ai/action-proposals/{id}/confirm` with an `Idempotency-Key`.

Organization admins can inspect immutable action/security events through
`GET /api/ai/audits`; conversation text is not exposed there.

## Tests

```bash
pytest
```
