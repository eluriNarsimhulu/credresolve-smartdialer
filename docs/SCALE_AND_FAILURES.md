# Scale and failure analysis

## Worker crash

Persisted call and reservation state survives process restart. However, a crash between reservation and provider callback can leave an in-flight call stuck. Production fix: use expiring reservation leases, durable provider request IDs, an outbox/inbox pattern, and a reconciler that queries provider state before releasing/retrying a call. Never blindly retry an uncertain call because that can create duplicate outbound calls.

## Provider outage

The demo can simulate provider failures and records failed outcomes. A production system should stop or sharply reduce new requests when timeouts rise, use a circuit breaker with half-open probes, apply bounded exponential backoff with jitter, and avoid retrying non-idempotent call creation unless the provider supports idempotency keys. Existing connected calls should not be terminated merely because new call setup is failing.

## Sudden agent drop

The safety controller derives capacity from current persisted `AVAILABLE` agents, not a stale dashboard count. In production, agent heartbeats and presence changes must update the authoritative store quickly; active calls must retain their reservation, while unassigned future calls must be cancelled or held. A drop from 100 to 60 available agents should immediately reduce new allocations to at most 60, less any capacity already committed.

## Duplicate / out-of-order events

Provider event IDs are unique and transitions are allow-listed. Terminal calls cannot be reopened. Production integrations also need provider-specific event ordering/version metadata, durable webhook acknowledgement, replay tooling, and alerting for contradictory event sequences.

## Growth from 100 to 10,000 agents

Likely early bottlenecks are a single SQLite writer, global allocation transactions, polling dashboards, and hot campaign queues. Move to a shared transactional database with row-level locking/atomic claims; partition work by campaign; keep an append-only event log; use bounded worker pools and queue backpressure; cache read-only dashboard aggregates; and measure p95/p99 setup latency, lock contention, event lag, and abandoned-call rate. Add complexity only after measuring the bottleneck.

## Security and compliance

This local assignment prototype is not production-ready. A real deployment needs authentication, authorization, encryption, secrets management, retention policies, borrower consent and eligibility checks, DNC/quiet-hours/jurisdiction safeguards, audit logging, and compliance review.
