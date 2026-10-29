"""Mock telecom provider interface and two deliberately different implementations.

No real phone calls are placed. These providers are deterministic profile definitions
used by the simulator and can be replaced by a real adapter behind the same contract.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class ProviderProfile:
    name: str
    latency_ms: int
    failure_rate: float
    duplicate_event_rate: float
    can_reorder_events: bool = False

class MockProvider:
    profile: ProviderProfile

    def get_profile(self) -> ProviderProfile:
        return self.profile

    def describe(self) -> dict:
        p = self.get_profile()
        return {"provider": p.name, "simulated_latency_ms": p.latency_ms,
                "configured_failure_rate": p.failure_rate,
                "duplicate_event_rate": p.duplicate_event_rate,
                "can_reorder_events": p.can_reorder_events}

class ProviderA(MockProvider):
    profile = ProviderProfile("A", latency_ms=40, failure_rate=0.05,
                              duplicate_event_rate=0.0, can_reorder_events=False)

class ProviderB(MockProvider):
    profile = ProviderProfile("B", latency_ms=180, failure_rate=0.20,
                              duplicate_event_rate=0.25, can_reorder_events=True)

def get_provider(name: str) -> MockProvider:
    providers = {"A": ProviderA, "B": ProviderB}
    try:
        return providers[name]()
    except KeyError as exc:
        raise ValueError("provider must be A or B") from exc
