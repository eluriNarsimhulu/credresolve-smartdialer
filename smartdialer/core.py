"""A small, safety-first SmartDialer prototype for the CredResolve hiring assignment."""
from __future__ import annotations
import random
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any
from .providers import get_provider

AGENT_STATES = {"OFFLINE", "AVAILABLE", "RESERVED", "DIALING", "CONNECTED", "WRAP_UP", "PAUSED"}
CALL_STATES = {"QUEUED", "RESERVED", "INITIATED", "RINGING", "ANSWERED", "CONNECTED", "COMPLETED", "FAILED", "CANCELLED"}
TERMINAL_CALL_STATES = {"COMPLETED", "FAILED", "CANCELLED"}
# Explicitly permitted forward transitions; terminal states cannot be reopened.
CALL_TRANSITIONS = {
    "QUEUED": {"RESERVED", "CANCELLED"},
    "RESERVED": {"INITIATED", "FAILED", "CANCELLED"},
    "INITIATED": {"RINGING", "ANSWERED", "FAILED", "CANCELLED", "COMPLETED"},
    "RINGING": {"ANSWERED", "FAILED", "CANCELLED", "COMPLETED"},
    "ANSWERED": {"CONNECTED", "COMPLETED", "FAILED"},
    "CONNECTED": {"COMPLETED", "FAILED"},
    "COMPLETED": set(), "FAILED": set(), "CANCELLED": set(),
}

class SmartDialer:
    def __init__(self, db_path: str = "smartdialer.db", seed_demo: bool = True):
        self.db_path = db_path
        self.lock = threading.RLock()
        self.rng = random.Random(7)
        self._init_db()
        if seed_demo and self.count("agents") == 0:
            self.seed_demo()

    @contextmanager
    def _connect(self):
        con = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _init_db(self):
        with self._connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS agents(
              id TEXT PRIMARY KEY, name TEXT NOT NULL, state TEXT NOT NULL,
              reserved_call_id TEXT, updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS borrowers(
              id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL,
              state TEXT NOT NULL DEFAULT 'QUEUED');
            CREATE TABLE IF NOT EXISTS calls(
              id TEXT PRIMARY KEY, borrower_id TEXT NOT NULL, agent_id TEXT,
              provider TEXT NOT NULL, state TEXT NOT NULL, created_at REAL NOT NULL,
              updated_at REAL NOT NULL, failure_reason TEXT,
              FOREIGN KEY(borrower_id) REFERENCES borrowers(id),
              FOREIGN KEY(agent_id) REFERENCES agents(id));
            CREATE TABLE IF NOT EXISTS provider_events(
              event_id TEXT PRIMARY KEY, call_id TEXT NOT NULL, event_type TEXT NOT NULL,
              received_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS decisions(
              id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
              requested INTEGER NOT NULL, approved INTEGER NOT NULL, reason TEXT NOT NULL);
            ''')

    def count(self, table: str) -> int:
        if table not in {"agents", "borrowers", "calls"}: raise ValueError("unsupported table")
        with self._connect() as c: return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def seed_demo(self, agents: int = 5, borrowers: int = 20):
        with self.lock, self._connect() as c:
            now = time.time()
            for i in range(1, agents + 1):
                c.execute("INSERT OR IGNORE INTO agents VALUES(?,?,?,?,?)", (f"A{i:03}", f"Agent {i}", "AVAILABLE", None, now))
            for i in range(1, borrowers + 1):
                c.execute("INSERT OR IGNORE INTO borrowers(id,name,phone,state) VALUES(?,?,?,'QUEUED')",
                          (f"B{i:04}", f"Borrower {i}", f"+910000{i:05}"))

    def _available_capacity(self, c) -> int:
        # Capacity is derived from current database state, not a cached UI count.
        return c.execute("SELECT COUNT(*) FROM agents WHERE state='AVAILABLE'").fetchone()[0]

    def _safety_approve_with_connection(self, c, requested: int, mode: str) -> tuple[int, str]:
        requested = max(0, int(requested))
        available = self._available_capacity(c)
        in_flight = c.execute("SELECT COUNT(*) FROM calls WHERE state IN ('RESERVED','INITIATED','RINGING','ANSWERED','CONNECTED')").fetchone()[0]
        queued = c.execute("SELECT COUNT(*) FROM borrowers WHERE state='QUEUED'").fetchone()[0]
        if mode == "progressive":
            approved = min(requested, available, queued)
        elif mode == "predictive":
            completed = c.execute("SELECT COUNT(*) FROM calls WHERE state IN ('COMPLETED','FAILED')").fetchone()[0]
            answered = c.execute("SELECT COUNT(*) FROM calls WHERE state IN ('ANSWERED','CONNECTED','COMPLETED')").fetchone()[0]
            answer_rate = answered / completed if completed else 0.35
            target = max(1, round(available / max(answer_rate, 0.1))) if available else 0
            approved = min(requested, available, queued, target)
            if in_flight >= available: approved = 0
        else:
            raise ValueError("mode must be progressive or predictive")
        reason = f"requested={requested}, available_agents={available}, queued_borrowers={queued}, in_flight={in_flight}, mode={mode}; approved={approved}"
        c.execute("INSERT INTO decisions(at,requested,approved,reason) VALUES(?,?,?,?)", (time.time(), requested, approved, reason))
        return approved, reason

    def safety_approve(self, requested: int, mode: str = "progressive") -> tuple[int, str]:
        with self.lock, self._connect() as c:
            return self._safety_approve_with_connection(c, requested, mode)

    def dial(self, mode: str = "progressive", requested: int | None = None, provider: str = "A") -> dict[str, Any]:
        if provider not in {"A", "B"}: raise ValueError("provider must be A or B")
        with self.lock, self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            available = c.execute("SELECT id FROM agents WHERE state='AVAILABLE' ORDER BY id").fetchall()
            queued = c.execute("SELECT id FROM borrowers WHERE state='QUEUED' ORDER BY id").fetchall()
            ask = requested if requested is not None else (1 if mode == "progressive" else max(1, len(available) * 2))
            # The safety controller is always the final gate. Never use predictive output directly.
            approved, reason = self._safety_approve_with_connection(c, ask, mode)
            n = min(approved, len(available), len(queued))
            made = []
            for agent, borrower in zip(available[:n], queued[:n]):
                call_id = str(uuid.uuid4())
                now = time.time()
                # Conditional updates make the reservation atomic at the database level.
                cur = c.execute("UPDATE agents SET state='RESERVED',reserved_call_id=?,updated_at=? WHERE id=? AND state='AVAILABLE'", (call_id, now, agent['id']))
                if cur.rowcount != 1: continue
                c.execute("UPDATE borrowers SET state='RESERVED' WHERE id=? AND state='QUEUED'", (borrower['id'],))
                c.execute("INSERT INTO calls VALUES(?,?,?,?,?,?,?,?)", (call_id, borrower['id'], agent['id'], provider, "INITIATED", now, now, None))
                c.execute("UPDATE agents SET state='DIALING' WHERE id=?", (agent['id'],))
                made.append({"call_id": call_id, "agent_id": agent['id'], "borrower_id": borrower['id'], "provider": provider, "state": "INITIATED"})
            c.commit()
        return {"mode": mode, "requested": ask, "approved": len(made), "reason": reason, "calls": made}

    def provider_event(self, call_id: str, event_type: str, event_id: str | None = None) -> dict[str, Any]:
        event_type = event_type.upper()
        if event_type not in {"RINGING", "ANSWERED", "CONNECTED", "COMPLETED", "FAILED", "CANCELLED"}:
            raise ValueError("unsupported event type")
        event_id = event_id or str(uuid.uuid4())
        with self.lock, self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT 1 FROM provider_events WHERE event_id=?", (event_id,)).fetchone():
                c.commit(); return {"accepted": False, "duplicate": True, "event_id": event_id}
            call = c.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
            if not call: c.rollback(); raise ValueError("unknown call_id")
            current = call["state"]
            # Store even stale/out-of-order events for audit, but never regress or reopen terminal calls.
            c.execute("INSERT INTO provider_events VALUES(?,?,?,?)", (event_id, call_id, event_type, time.time()))
            if event_type not in CALL_TRANSITIONS.get(current, set()):
                c.commit(); return {"accepted": False, "duplicate": False, "stale": True, "current_state": current, "event_id": event_id}
            now = time.time()
            c.execute("UPDATE calls SET state=?,updated_at=?,failure_reason=? WHERE id=? AND state=?",
                      (event_type, now, "provider failure" if event_type == "FAILED" else None, call_id, current))
            if event_type in {"ANSWERED", "CONNECTED"}:
                c.execute("UPDATE agents SET state=?,updated_at=? WHERE id=? AND reserved_call_id=?",
                          ("CONNECTED", now, call["agent_id"], call_id))
                c.execute("UPDATE borrowers SET state='CONTACTED' WHERE id=?", (call["borrower_id"],))
            if event_type in TERMINAL_CALL_STATES:
                c.execute("UPDATE agents SET state='AVAILABLE',reserved_call_id=NULL,updated_at=? WHERE id=? AND reserved_call_id=?",
                          (now, call["agent_id"], call_id))
                c.execute("UPDATE borrowers SET state='DONE' WHERE id=?", (call["borrower_id"],))
            c.commit()
            return {"accepted": True, "duplicate": False, "state": event_type, "event_id": event_id}

    def simulate(self, scenario: str = "normal", mode: str = "progressive", requested: int | None = None, provider: str | None = None) -> dict[str, Any]:
        provider = provider or ("B" if scenario in {"duplicates", "out_of_order", "outage"} else "A")
        if provider not in {"A", "B"}: raise ValueError("provider must be A or B")
        # Mock provider profiles deliberately differ. No network/telephony calls are made.
        provider_adapter = get_provider(provider)
        profile = provider_adapter.get_profile()
        result = self.dial(mode, requested, provider)
        events = []
        for call in result["calls"]:
            cid = call["call_id"]
            if scenario == "outage" or (scenario == "normal" and self.rng.random() < profile.failure_rate):
                event = "FAILED"
            elif scenario == "low_answer": event = "FAILED" if self.rng.random() < 0.9 else "ANSWERED"
            else: event = "ANSWERED" if self.rng.random() < 0.5 else "FAILED"
            if scenario == "out_of_order" and event == "FAILED":
                events.append(self.provider_event(cid, "COMPLETED", f"{cid}-late-completed"))
                events.append(self.provider_event(cid, "ANSWERED", f"{cid}-late-answered"))
            else:
                events.append(self.provider_event(cid, event, f"{cid}-event-1"))
                if scenario == "duplicates" or self.rng.random() < profile.duplicate_event_rate:
                    events.append(self.provider_event(cid, event, f"{cid}-event-1"))
        return {"dial": result, "events": events, "scenario": scenario,
                "provider_profile": provider_adapter.describe()}

    def simulate_agent_drop(self, count: int = 1) -> dict[str, Any]:
        """Simulate agents disappearing; active calls are failed safely and borrowers re-queued."""
        count = max(0, int(count))
        with self.lock, self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            rows = c.execute("SELECT id, state, reserved_call_id FROM agents WHERE state IN ('AVAILABLE','RESERVED','DIALING') ORDER BY CASE WHEN reserved_call_id IS NOT NULL THEN 0 ELSE 1 END, id DESC LIMIT ?", (count,)).fetchall()
            now = time.time()
            affected = []
            for row in rows:
                call_id = row['reserved_call_id']
                if call_id:
                    call = c.execute("SELECT borrower_id,state FROM calls WHERE id=?", (call_id,)).fetchone()
                    if call and call['state'] not in TERMINAL_CALL_STATES:
                        c.execute("UPDATE calls SET state='FAILED',updated_at=?,failure_reason='agent became unavailable during setup' WHERE id=?", (now, call_id))
                        c.execute("UPDATE borrowers SET state='QUEUED' WHERE id=?", (call['borrower_id'],))
                c.execute("UPDATE agents SET state='OFFLINE',reserved_call_id=NULL,updated_at=? WHERE id=?", (now, row['id']))
                affected.append(row['id'])
            c.commit()
            return {"dropped_agents": affected, "count": len(affected)}

    def recover_stale_calls(self, stale_seconds: float = 30.0) -> dict[str, Any]:
        """Reconcile calls left in setup states after a worker crash or lost provider callback."""
        cutoff = time.time() - max(0.0, float(stale_seconds))
        with self.lock, self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            rows = c.execute("SELECT id,agent_id,borrower_id,state FROM calls WHERE state IN ('RESERVED','INITIATED','RINGING') AND updated_at<=?", (cutoff,)).fetchall()
            now = time.time()
            recovered = []
            for row in rows:
                c.execute("UPDATE calls SET state='FAILED',updated_at=?,failure_reason='stale call recovered after worker/provider timeout' WHERE id=? AND state IN ('RESERVED','INITIATED','RINGING')", (now, row['id']))
                c.execute("UPDATE agents SET state='AVAILABLE',reserved_call_id=NULL,updated_at=? WHERE id=? AND reserved_call_id=?", (now, row['agent_id'], row['id']))
                c.execute("UPDATE borrowers SET state='QUEUED' WHERE id=?", (row['borrower_id'],))
                recovered.append(row['id'])
            c.commit()
            return {"recovered_calls": recovered, "count": len(recovered)}

    def state(self) -> dict[str, Any]:
        with self._connect() as c:
            agents = [dict(r) for r in c.execute("SELECT * FROM agents ORDER BY id")]
            borrowers = [dict(r) for r in c.execute("SELECT * FROM borrowers ORDER BY id")]
            calls = [dict(r) for r in c.execute("SELECT * FROM calls ORDER BY created_at DESC LIMIT 100")]
            decisions = [dict(r) for r in c.execute("SELECT * FROM decisions ORDER BY id DESC LIMIT 30")]
            totals = {"agents": len(agents), "available_agents": sum(a["state"] == "AVAILABLE" for a in agents),
                      "connected_calls": sum(x["state"] in {"ANSWERED", "CONNECTED"} for x in calls),
                      "calls_initiated": c.execute("SELECT COUNT(*) FROM calls").fetchone()[0],
                      "completed_calls": c.execute("SELECT COUNT(*) FROM calls WHERE state='COMPLETED'").fetchone()[0],
                      "failed_calls": c.execute("SELECT COUNT(*) FROM calls WHERE state='FAILED'").fetchone()[0],
                      "utilization_pct": round(100 * sum(a["state"] in {"DIALING", "CONNECTED", "RESERVED"} for a in agents) / len(agents), 1) if agents else 0}
            return {"agents": agents, "borrowers": borrowers, "calls": calls, "decisions": decisions, "metrics": totals}
