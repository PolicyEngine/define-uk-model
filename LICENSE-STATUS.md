# Upstream licensing status — DEFINE-UK

**Position: the upstream model is unlicensed. Everything this repository
produces is replication-only until that is resolved.**

## The facts

- Upstream: [DEFINE-model/DEFINE_UK_1.1](https://github.com/DEFINE-model/DEFINE_UK_1.1)
  (Dafermos, Nikolaidi, George and co-authors; define-model.org). The
  repository is public on GitHub but **carries no license file and no
  license grant of any kind**. Under default copyright, "public on GitHub"
  does not permit copying, redistribution, hosting, or derivative works.
- Consequently this repository **never vendors, copies, hosts, or
  redistributes** any upstream code or data. `define_uk.upstream` fetches
  the upstream repository at a **pinned commit**
  (`846081a580a6033159d5c421632ad8f0b30d0ded`, `DEFINE_UK_1.1@main` as of
  2026-08-01) into a local cache on the user's own machine, and
  `define_uk.runner` executes it there in R. Bumping the pin is an
  explicit, reviewed change tied to `validation/reference_outputs.json`.
- Code written in this repository (the adapter, tests, and the clean-room
  reimplementation under `src/define_uk/model/`) is AGPL-3.0 (see
  `LICENSE`), the PolicyEngine convention. The clean-room work follows the
  protocol in `REIMPLEMENTATION.md`: it is derived from the published
  Model Manual v1.1, using the upstream code only as a numerical oracle
  run locally.

## What this means for presenting results

- Results from the upstream run are a **validated replication of the
  pinned commit**, nothing more: scenario-minus-baseline deltas gated by
  the CI validation gate (see `VALIDATION.md`, "Acceptance criteria").
- Nothing built on this repository may host the upstream code, serve its
  outputs as a live model, or present its baseline levels as forecasts.
- CI never fetches or runs the upstream code; the CI gate operates on
  committed reference artifacts recorded from local pinned runs.

## What resolution would require

Any of the following, in descending order of completeness:

1. **An OSI-approved license added upstream** (the request to the DEFINE
   team is the first item on the README roadmap). That would permit
   vendoring at a pinned revision — the pattern used by
   [us-frb-model](https://github.com/PolicyEngine/us-frb-model) — and,
   depending on the license, hosting.
2. **Written permission from the authors** for a defined scope (e.g.
   vendoring and hosting outputs with attribution), recorded in this file
   with date and scope.
3. **Completion of the clean-room reimplementation** (`REIMPLEMENTATION.md`,
   `src/define_uk/model/`) validated against the oracle to the tolerances
   in `VALIDATION.md` — at which point the hostable artifact is our own
   AGPL-3.0 code, credited to the DEFINE authors as an independent
   implementation of their published design, and the upstream code is no
   longer needed at run time.

Until one of these happens, the licensing position above is the operative
constraint on every downstream surface (policyengine-macro's
`define_scenario`, the site, MCP tools): **replication-only, deltas-only,
local-cache-only.**
