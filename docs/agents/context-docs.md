# Context Docs

Where this repo's Context docs live and how the engineering skills use them.

## Paths

Single-context repo.

- Glossary: `GLOSSARY.md`
- ADRs: `docs/adr/`
- Architecture doc: `ARCHITECTURE.md`
- Specs: `docs/specs/NNNN-<slug>.md`, index at `docs/specs/README.md`

Scratch work lives in `.scratch/<effort>/`.

## What to read

The Orient step (`ORIENT.md` in the `interview` skill) owns the reading path: which of these docs to read for a concern, and in what order.

## Use the glossary's vocabulary

When your output names a domain concept (an issue title, a refactor proposal, a hypothesis, a test name), use the term as the glossary defines it. A term the glossary lacks is either invented language (reconsider) or a gap (note it for `domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, say so rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
