# CredResolve SmartDialer — hiring assignment prototype

A local, safety-first SmartDialer simulation built with Python's standard library, SQLite, and a browser UI. It is a prototype, not a real telecom integration.

## Features

- Progressive dialing and a conservative rule-based predictive pacing request.
- A separate Safety Controller is the final gate for every dial request.
- Explicit agent and call states, conditional agent reservation, and SQLite transactions.
- Provider adapter interface with two mock providers: A (fast/reliable) and B (slower, more failures and duplicate/out-of-order events).
- Simulated agent disappearance and stale-call reconciliation after a worker/provider timeout.
- Idempotent provider event IDs and protection against terminal calls being reopened by late events.
- Dashboard with agent utilization, call state, and safety-decision audit log.
- Unit tests and a small HTTP health-endpoint load smoke test.

## Requirements

Python 3.10+; no third-party packages required. **No dependencies are bundled or installed by this project.** It uses only the Python standard library and SQLite included with Python.

## Run locally

```bash
python app.py
```

Open http://127.0.0.1:8000. The app seeds 5 agents and 20 borrowers on first run. The SQLite database is created as `smartdialer.db` in the project root.

To use a separate database path:

```bash
SMARTDIALER_DB=/tmp/smartdialer-demo.db python app.py
```

## Tests

Run from this folder:

```bash
python -m unittest discover -s tests -v
```

A sample output is included at `results/scenario_results.csv`. Re-run the transparent A–D scenario model (writes a CSV report; synthetic assumptions, not observed data):

```bash
python simulate_scenarios.py --agents 100 --horizon 600 --output scenario_results.csv
```

With the server running, run the lightweight API smoke test:

```bash
python load_test.py
```

This measures local health endpoint throughput only; it is not a production load test.

## API

- `GET /api/health` — liveness check.
- `GET /api/state` — agents, borrowers, recent calls, metrics, and safety decisions.
- `POST /api/dial` — JSON such as `{"mode":"progressive","requested":3,"provider":"A"}`.
- `POST /api/simulate` — JSON such as `{"mode":"predictive","scenario":"duplicates","provider":"B"}`.
- `POST /api/event` — apply a mock event: `{"call_id":"...","event_type":"FAILED","event_id":"unique-id"}`.
- `POST /api/seed` — add demo agents/borrowers; it does not delete existing records.
- `POST /api/agent-drop` — simulate agents disappearing, failing any active setup call and re-queueing its borrower. Example: `{"count":2}`.
- `POST /api/recover` — reconcile stale `RESERVED`/`INITIATED`/`RINGING` calls. Example: `{"stale_seconds":30}`.

Simulation scenarios: `normal`, `low_answer`, `duplicates`, `out_of_order`, `outage`.

## Important design decisions and limitations

1. **Safety first:** The predictive path requests work but cannot directly contact a provider. The Safety Controller independently checks current database state and caps agent-bound calls by available agents and queued borrowers.
2. **Concurrency:** `BEGIN IMMEDIATE`, conditional `UPDATE ... WHERE state='AVAILABLE'`, and a process-local reentrant lock reduce races in this local prototype. The process-local lock is not a distributed lock. For multiple service instances, use a shared database transaction/locking strategy and enforce unique active reservations at the database level.
3. **Idempotency:** `provider_events.event_id` is a primary key. Replaying an event ID has no second effect. Stale/out-of-order transitions are audited and ignored rather than regressing state.
4. **Provider abstraction:** Providers are represented by provider IDs and scenario-driven event behavior. No real phone call or external provider SDK is used.
5. **Pacing trade-off:** This first prototype deliberately uses a conservative cap on agent-bound calls. It demonstrates safe pacing, not a full predictive dialer that starts unbound calls before agents are free. A production version would need an explicit orphan/abandoned-call risk budget and atomic agent assignment at answer time.
6. **Crash recovery:** State is persisted in SQLite, so a restart preserves the last committed state. A production service should add reservation leases, a reconciler for stuck `INITIATED`/`RINGING` calls, retry policy, durable event ingestion, and alerting.
7. **Compliance:** This demo does not implement real consent, DNC, quiet-hour, jurisdiction, retention, or regulatory checks. Do not connect it to real borrowers or a telecom provider without those controls and a proper review.

## Suggested demo flow

1. Select Progressive and click **Dial only**; show that calls do not exceed available agents.
2. Refresh and show reserved/dialing agents.
3. Choose **Duplicate provider events** and click **Run simulation**; inspect the audit and call state.
4. Choose **Out-of-order events**; show that a terminal call is not reopened by a late answer.
5. Choose **Provider outage**; show failure handling and agent release.
6. Switch to Predictive, request 50 calls, and explain why the Safety Controller still caps agent-bound calls.

## GitHub submission checklist

- [ ] Run tests and paste the result in your own submission notes.
- [ ] Run the app from a clean terminal.
- [ ] Capture a dashboard screenshot if useful.
- [ ] Review and understand every design decision you plan to discuss.
- [ ] Push source, tests, README, architecture diagram, and ADR to a public or recruiter-accessible repository.
- [ ] Submit the repository URL using the recruitment form before the stated deadline.

Architecture diagram: [`docs/architecture.svg`](docs/architecture.svg). State machines: [`docs/STATE_MACHINES.md`](docs/STATE_MACHINES.md). Architecture and data-flow notes: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Requirement map: [`docs/REQUIREMENT_COVERAGE.md`](docs/REQUIREMENT_COVERAGE.md).
