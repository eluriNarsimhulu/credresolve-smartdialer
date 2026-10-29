# Architecture

```mermaid
flowchart LR
  UI[Browser dashboard] --> API[Python HTTP API]
  API --> Campaign[Campaign / request handler]
  Campaign --> Pace[Progressive or Predictive Pacing]
  Pace --> Safety[Safety Controller]
  Safety --> Alloc[Transactional Call Allocator]
  Alloc --> DB[(SQLite state + event log)]
  Alloc --> Mock[Mock Telecom Provider A/B]
  Mock --> Events[Provider event handler]
  Events --> DB
  DB --> API
```

The pacing engine proposes a requested count. It does not have provider access. The Safety Controller reads current agent/borrower/call state and limits the approved count. The allocator then conditionally reserves agents and borrowers inside a database transaction. Provider callbacks are applied through a separate event handler.

## Agent state machine

```mermaid
stateDiagram-v2
  [*] --> AVAILABLE
  AVAILABLE --> RESERVED: reserve atomically
  RESERVED --> DIALING: call initiated
  DIALING --> CONNECTED: answered/connected
  DIALING --> AVAILABLE: failed/cancelled and release
  CONNECTED --> AVAILABLE: completed/failed and release
  AVAILABLE --> PAUSED: agent pauses
  PAUSED --> AVAILABLE: resume
  AVAILABLE --> OFFLINE: agent signs out
  OFFLINE --> AVAILABLE: agent signs in
  CONNECTED --> WRAP_UP: conversation ends
  WRAP_UP --> AVAILABLE: wrap-up complete
```

The prototype implements the core states needed for allocation and cleanup. `PAUSED`, `OFFLINE`, and `WRAP_UP` are documented lifecycle states but are not yet exposed as UI actions.

## Call state machine

```mermaid
stateDiagram-v2
  [*] --> QUEUED
  QUEUED --> RESERVED
  RESERVED --> INITIATED
  INITIATED --> RINGING
  INITIATED --> ANSWERED
  INITIATED --> FAILED
  INITIATED --> COMPLETED
  RINGING --> ANSWERED
  RINGING --> FAILED
  ANSWERED --> CONNECTED
  ANSWERED --> COMPLETED
  CONNECTED --> COMPLETED
  CONNECTED --> FAILED
  FAILED --> [*]
  COMPLETED --> [*]
  CANCELLED --> [*]
```

The implementation keeps an explicit transition allow-list. Duplicate event IDs are ignored, and a terminal state cannot be reopened.
