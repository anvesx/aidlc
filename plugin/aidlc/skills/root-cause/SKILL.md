---
name: root-cause
description: How AIDLC finds the real cause of a failure or bug - reproduce it first, trace it to its cause rather than the symptom, then name which step the cause is in (Build, Plan, Clarify, the TDD or the PRD). Use for bug work in Clarify and whenever a check fails.
---

# Root cause

A fix that hides the symptom leaves the cause in place, and it comes back. Find the cause first.

## 1. Reproduce it

- Write the exact steps, the input, what happens, and what should happen.
- Run them and see it fail yourself. Save the evidence (output, error, screenshot path).
- **If you can't reproduce it, stop.** Say what you tried and ask the person for more information. Never fix based on a guess.

## 2. Narrow it down

- Find the smallest input or step that still fails.
- Read the code on the path the failure takes. Use the `aidlc:code-reader` agent for a large area.
- Check what changed recently around it (`git log` on those files).
- Form one explanation at a time and test it. Keep a short list of what you ruled out and how.

## 3. Name the cause, not the symptom

Ask "why?" until the answer is something that was decided or built wrong.

| Symptom | Not the cause | The cause |
|---|---|---|
| Total shows NaN | "The total is wrong" | The discount field can be empty, and the code adds it without a default |

The cause must explain **every** observed failure. If it explains only some, keep going.

## 4. Find which step the cause is in

| The cause is... | Step |
|---|---|
| Code that doesn't do what the plan said | Build |
| A plan that, followed exactly, still fails | Plan |
| A "done" item or need that was wrong or missing | Clarify |
| A shared decision in the TDD | Outer Plan (TDD) |
| A requirement in the PRD | Outer Clarify (PRD) |
| A test that checks the wrong thing, while the code is right | Clarify (the "done" list) or the test itself; tell the person |

Then follow the "Going back" table in the rules.

## 5. Report it

In plain words: what failed, the evidence, the cause, which step it's in, and what you propose. Add the cause to `learnings.md` at Record, so it isn't repeated.
