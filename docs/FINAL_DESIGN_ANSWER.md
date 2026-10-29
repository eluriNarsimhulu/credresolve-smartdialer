# Final design question

**How would I obtain predictive-dialing utilization benefits while retaining progressive dialing's deterministic safety?**

I would separate pacing from authorization. A pacing engine may estimate how many calls are likely to connect using rolling, campaign-specific answer rates, setup latency, agent occupancy, and provider health. It can only submit a proposed count; it has no credentials or direct code path to the telecom provider.

A Safety Controller then reads authoritative agent and call state and enforces hard limits: no more agent-bound calls than available agents, no duplicate active reservation for an agent or borrower, campaign eligibility checks, and an explicit abandoned-call risk budget. The allocator reserves an agent and borrower atomically and uses idempotency keys for call creation. If state is stale, provider health degrades, or the safety budget is uncertain, the controller reduces the request or falls back to progressive dialing.

Provider events enter through a durable, idempotent event handler. Duplicate events are ignored, invalid/out-of-order transitions are audited, and terminal calls cannot reopen. Leases and reconciliation recover worker crashes without blindly redialing uncertain calls. I would validate the design with concurrency tests, provider-failure injection, changing answer-rate/talk-time simulations, and load tests measuring agent utilization, connection rate, abandoned calls, event lag, and safety-controller decisions.

The central principle is that predictive logic can optimize efficiency, but it cannot weaken the deterministic safety boundary.
