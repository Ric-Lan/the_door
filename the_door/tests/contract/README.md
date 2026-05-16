# Contract Tests — Tier Seam Verification

Each file here pins the *interface* between two task tiers. Producer and consumer task
suites both reference these contracts.

## How to consume

- A contract test starts with `pytest.skip("blocked on <task-id>")`.
- When the producer task lands, that task's commit removes the skip from the
  producer-side assertion (the part that constructs the contract value from the
  real producer).
- When the consumer task lands, that task's commit removes the skip from the
  consumer-side assertion (the part that feeds the contract value to the consumer
  and asserts behavior).
- Both sides live in the same test — the seam can only go GREEN when BOTH tiers
  are correct AND aligned.

## Why not put these in `unit/` or `integration/`?

`unit/` tests verify ONE module's behavior. `integration/` tests verify a flow.
Contract tests are neither — they verify that the *boundary* between two modules
agrees on shape and semantics. Misplacing them in either bucket dilutes that signal.
