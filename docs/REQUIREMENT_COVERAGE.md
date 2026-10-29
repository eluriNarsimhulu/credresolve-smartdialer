# Assignment requirement coverage

This document maps the submitted prototype to the CredResolve `Tech Assignment – Hiring 2026` requirements. Be precise in any interview: a local prototype is not a production telephony platform.

| Assignment requirement | Included | Notes / limitation |
|---|---|---|
| Working source code and README | Yes | Python standard-library HTTP server, SQLite and browser dashboard. |
| Progressive Dialer | Yes | Allocates only currently available agents and queued borrowers. |
| Predictive Pacing Engine | Partial | Rule-based requested count based on observed answer outcomes; intentionally conservative. It does not yet originate unbound predictive calls. |
| Separate Safety Controller | Yes | Final gate checks live DB state; allocation occurs inside a transaction. |
| Explicit agent and call states | Yes, core states | State machines documented in `ARCHITECTURE.md`; PAUSED/OFFLINE/WRAP_UP are documented but not all exposed as UI actions. |
| Concurrent agent allocation | Local prototype covered | SQLite `BEGIN IMMEDIATE`, conditional state update, process lock and concurrency unit test. A multi-instance deployment needs shared DB-level coordination and stronger invariant constraints. |
| Provider abstraction and two mock providers | Yes, mock adapters | `smartdialer/providers.py` defines a provider contract and Provider A/B profiles; no real telecom integration. |
| Duplicate and out-of-order provider events | Yes, basic | Unique event IDs and transition allow-list; stale events are audited and ignored. |
| Worker crash recovery | Basic reconciliation implemented | `POST /api/recover` marks stale setup calls failed, releases matching agents and re-queues borrowers. No background scheduler/lease heartbeat is included. |
| Provider outage handling | Basic simulation | Outage scenario fails newly simulated calls; circuit breaker, retry queue and provider health-based pacing are not production-grade. |
| Sudden agent availability drop | Basic API simulation | `POST /api/agent-drop` marks agents offline and safely resolves active setup calls. No heartbeat service is included. |
| Predictive scenarios A-D / utilization analysis | Basic transparent scenario model | `simulate_scenarios.py` produces A–D CSV estimates for answer-rate/talk-time/provider assumptions, initiated/connected calls and estimated utilization. It is a simplified synthetic model, not a calibrated time-stepped simulator. |
| Tests | Yes, basic | Run `python -m unittest discover -s tests -v` (11 tests currently pass). |
| Basic load test | Yes, smoke test | `load_test.py` measures local health endpoint throughput only, not 10k calls/sec or full workload performance. |
| Architecture diagram | Yes | `architecture.svg` and Mermaid in `ARCHITECTURE.md`. |
| Short architecture decision document | Yes | `ADR-001.md`. |
| Scale analysis | Yes, written | See `SCALE_AND_FAILURES.md`. |
| Final design question | Yes, written | See `FINAL_DESIGN_ANSWER.md`. |

## Known production gaps

Before connecting to real borrowers or telecom, implement and test: reservation leases and reconciliation, an explicit abandoned-call risk budget, provider circuit breakers and bounded retries, agent presence/heartbeat handling, campaign/borrower eligibility and consent checks, quiet-hour/DNC controls, audit retention, authentication/authorization, observability, and a true multi-process load test. This prototype deliberately uses mock phone data and does not place calls.
