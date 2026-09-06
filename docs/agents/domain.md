# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root
- **`docs/adr/`** — read ADRs that touch the area you're about to work in
- **`SPEC.md`** and **`AGENT.md`** when the work touches product story, invariants, or Layout

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The producer skill (`/grill-with-docs`) creates them lazily when terms or decisions actually get resolved.

`.scratch/` holds in-progress PRDs and implementation slices. It does not replace `SPEC.md`, `CONTEXT.md`, or ADRs.

## File structure

Single-context repo:

```
/
├── CONTEXT.md
├── SPEC.md
├── AGENT.md
├── docs/adr/
├── docs/runtime-flows.md   # Prefect write + retrieve/chat read
├── docs/agents/
├── backend/
├── frontend/lending/
└── .scratch/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/grill-with-docs`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0005 (CAUSED decision chain) — but worth reopening because…_
