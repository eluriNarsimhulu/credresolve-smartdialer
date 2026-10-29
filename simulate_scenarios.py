"""Transparent, dependency-free A-D pacing scenario simulator.

This is a planning model, not production telemetry or a calibrated forecasting model.
Run: python simulate_scenarios.py [--agents 100 --horizon 600 --output scenario_results.csv]
"""
import argparse, csv, random
from pathlib import Path

SCENARIOS = [
    {"scenario":"A", "answer_rate":0.20, "avg_talk_seconds":120, "provider_latency_seconds":0.4, "provider_failure_rate":0.05},
    {"scenario":"B", "answer_rate":0.50, "avg_talk_seconds":90, "provider_latency_seconds":0.4, "provider_failure_rate":0.05},
    {"scenario":"C", "answer_rate":0.70, "avg_talk_seconds":180, "provider_latency_seconds":1.8, "provider_failure_rate":0.20},
    {"scenario":"D", "answer_rate":0.35, "avg_talk_seconds":150, "provider_latency_seconds":1.0, "provider_failure_rate":0.10},
]

def simulate(agents, horizon, seed=17):
    rng = random.Random(seed)
    rows = []
    for cfg in SCENARIOS:
        # Demand is intentionally bounded. Predictive request may be larger, but
        # the safety controller only approves agent-bound calls up to free capacity.
        queue_size = agents * 20
        free_agents = agents
        requested = min(queue_size, max(agents, round(agents / max(cfg["answer_rate"], .1))))
        approved = min(requested, free_agents, queue_size)
        initiated = approved
        outcomes = [rng.random() for _ in range(initiated)]
        connected = sum(x < cfg["answer_rate"] and x >= cfg["provider_failure_rate"] for x in outcomes)
        failed = initiated - connected
        busy_agent_seconds = min(agents * horizon, connected * cfg["avg_talk_seconds"])
        utilization = 100 * busy_agent_seconds / (agents * horizon) if agents and horizon else 0
        rows.append({
            "scenario": cfg["scenario"], "answer_rate_assumption": cfg["answer_rate"],
            "avg_talk_seconds": cfg["avg_talk_seconds"],
            "provider_latency_seconds": cfg["provider_latency_seconds"],
            "provider_failure_rate_assumption": cfg["provider_failure_rate"],
            "agents": agents, "calls_requested_by_pacer": requested,
            "calls_approved_by_safety": approved, "calls_initiated": initiated,
            "calls_connected_estimate": connected, "calls_not_connected_estimate": failed,
            "safety_cap_respected": approved <= free_agents,
            "estimated_talk_utilization_pct": round(utilization, 2),
            "interpretation": "synthetic estimate; latency impact is shown as an input, not time-stepped"
        })
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--agents', type=int, default=100)
    parser.add_argument('--horizon', type=int, default=600, help='simulation window in seconds')
    parser.add_argument('--output', default='scenario_results.csv')
    args = parser.parse_args()
    if args.agents < 1 or args.horizon < 1:
        parser.error('--agents and --horizon must be positive')
    rows = simulate(args.agents, args.horizon)
    output = Path(args.output)
    with output.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(f"Wrote {len(rows)} scenario rows to {output}")
    print("Scenario | requested | safety-approved | initiated | connected est. | utilization est.")
    for r in rows:
        print(f"{r['scenario']:>8} | {r['calls_requested_by_pacer']:>9} | {r['calls_approved_by_safety']:>14} | {r['calls_initiated']:>9} | {r['calls_connected_estimate']:>14} | {r['estimated_talk_utilization_pct']:>16.2f}%")

if __name__ == '__main__': main()
