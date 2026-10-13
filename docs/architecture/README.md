# AirYatra Architecture (Azure)

| Document | Contents |
|---|---|
| [01-target-architecture.md](01-target-architecture.md) | Phase 1: stage 1 (1K users) and stage 2 (20K users) diagrams, decision log, capacity and cost, scale triggers, Atlas vs Cosmos vCore, risks |
| [02-sequence-diagrams-high-level.md](02-sequence-diagrams-high-level.md) | 8 system-level sequence diagrams: request path, booking, money flow, real-time, scheduler, CI/CD, migration, DR |
| [03-sequence-diagrams-low-level.md](03-sequence-diagrams-low-level.md) | 15 code-level sequence diagrams for the Q.2 critical journeys, with today's file:line and the Phase 3 gaps |
| [04-threat-model.md](04-threat-model.md) | STRIDE threat model and abuse cases |
| [`infra/terraform/`](../../infra/terraform/README.md) | Terraform for dev and prod, with apply steps |
| [`docs/phase0/`](../phase0/README.md) | Phase 0 discovery: data dictionary, dependencies, security audit, code map |

All diagrams are Mermaid and render on GitHub. They were checked with `@mermaid-js/mermaid-cli` 11.4.2.
