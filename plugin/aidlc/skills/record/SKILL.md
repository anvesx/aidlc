---
name: record
description: The AIDLC Record step. Writes learnings.md and promotes anything that matters beyond this work into aidlc/decisions/, aidlc/standards/ and aidlc/index.md, so the next session starts with it. Runs for each feature, bug fix and unit, and once for the whole of a project or new module after the final check. Use when AIDLC work is at the Record step.
---

# Record

**Job:** make sure the next person or session doesn't repeat this work's mistakes or re-ask its settled questions. A feature, bug fix or unit is not finished until this step is `Done`.

Before starting: read `${CLAUDE_PLUGIN_ROOT}/skills/aidlc/rules.md` if you haven't this session.

## Expertise: what is worth recording

Keep it short. Record only what the code does not already say clearly.

| Worth recording | Not worth recording |
|---|---|
| Why a choice was made, and what was rejected | What the code does |
| Something that surprised you or broke unexpectedly | A step-by-step diary |
| A rule that should apply to future work | Things that only matter inside this one change |
| An assumption that turned out wrong | Anything already in `decisions/` or `standards/` |
| A gap in AIDLC itself (a template or skill that misled you) | |

## Steps (driver session)

1. Create `learnings.md` from `${CLAUDE_PLUGIN_ROOT}/templates/learnings.md` (for the whole of a project or new module, the driver already created it with a `Claimed by:` line: fill it in and keep that line). Read the work's files (`clarify.md`, `plan.md`, `build-log.md`, `check-assessment.md`) for decisions, changes from the plan, and failures.
2. Write the learnings: decisions made here (and why), what was learned, what went wrong and its cause.
3. **A unit:** do not edit `aidlc/index.md`, `aidlc/decisions/`, `aidlc/standards/` or `aidlc/project.md`. List each item that should be promoted (decision, proposed standard, project fact) under "To promote" in `learnings.md`, then go to step 5. The Record of the whole work promotes them.

   **A feature, a bug fix, or the whole of a project or new module: promote** what matters beyond this work:
   - **A decision** that fixes direction or scope, or is shared or hard to undo: create `aidlc/decisions/D-NNN-<name>.md` from `${CLAUDE_PLUGIN_ROOT}/templates/decision.md` (next free number). If it replaces an active decision, the old one may only be changed to `Status: Replaced by D-NNN`. List everything the old decision affected in the new one, and post in Slack that that work must be checked.
   - **A new rule** for how work is done: standards affect everyone, so this is a person's decision. Write the proposed change in `learnings.md` under "Proposed standards" and ask (`Waiting for answers`, tag the person on the `Claimed by:` line, or the tech lead for the whole). Apply it to `aidlc/standards/<topic>.md` only after a yes.
   - **Project facts** that changed (how to run, test or deploy): update `aidlc/project.md`.
   - **A gap in AIDLC itself:** note it under "AIDLC feedback" in `learnings.md`.
4. Update `aidlc/index.md`: any new decision or standard with its one-line summary.
5. Set `learnings.md` to `Status: Done` and end. The driver commits and pushes, and starts the next stage (the PR for a feature or bug fix; the next unit or the phase check for a unit).

## The whole of a project or new module

Same steps, in the task folder, after the final check is approved. First collect every unit's "To promote" list (all `learnings.md` files under the task folder), then promote them together with the learnings that apply to the whole project. Ask about all proposed standards in one round.

## Never

- Edit an active decision's content. Replace it with a new one.
- Change a standard without a person's yes.
- Record what the code already says.
