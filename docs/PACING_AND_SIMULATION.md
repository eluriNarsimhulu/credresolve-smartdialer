# Pacing and simulation

## Prototype pacing rule

Progressive mode asks for one call by default and the Safety Controller caps allocations to the live count of `AVAILABLE` agents and queued borrowers. Predictive mode estimates a request from observed answer outcomes, but the same independent Safety Controller remains the final gate. This deliberately prioritizes not creating more agent-bound calls than available agents. It is not a full predictive dialer that starts unbound calls ahead of agent availability.

## A–D scenario model

Run `python simulate_scenarios.py --agents 100 --horizon 600 --output scenario_results.csv`. It models the assignment's example conditions: A 20% answer rate / 120-second talk time; B 50% / 90 seconds; C 70% / 180 seconds; D changing-like midpoint assumptions. It also records provider latency and failure assumptions.

The script is intentionally transparent and dependency-free. It produces synthetic estimates and does not model a full event-by-event timeline, queueing distribution, confidence intervals, or calibrated historic behavior. Latency is reported as an input but is not used to calculate utilization. State these limitations rather than presenting simulated estimates as measured business performance.

## Interpretation

A production-grade pacing engine should use rolling, confidence-aware answer-rate estimates, provider health, ringing calls, agent availability, average talk time and a strict abandoned-call risk budget. The pacing engine can propose a number, but must never invoke a provider directly.
