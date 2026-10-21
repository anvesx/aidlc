---
name: build
description: The AIDLC Build step. Builds the code from plan.md (tests first, by the test-writer agent) and logs any change from the plan in build-log.md. Runs in a driver session in Claude Code, for a feature, a bug fix or one unit (on its module's branch). Use when AIDLC work is at the Build step.
---

# Build

**Job:** build what the plan says. Build makes no design decisions; the plan already made them.

Before starting: read `${CLAUDE_PLUGIN_ROOT}/skills/aidlc/rules.md` if you haven't this session.

## Expertise

- **Tests first.** The `aidlc:test-writer` agent writes the tests from `clarify.md` and `plan.md` before any code exists, so the tests can't copy the code's mistakes.
- **One TODO at a time.** Finish it, run the related tests, then move to the next.
- **Follow the project's standards** (`aidlc/standards/`) and the patterns already in the code around you.
- **Changes from the plan are logged, never hidden.** Small change (no "done" item or shared decision affected): log it and carry on. Anything bigger: go back to Plan.
- **Never change a test to make it pass.** If a test looks wrong, that is a Clarify or Plan question, not a Build fix.

## Branch

The driver already put this session on the right branch (`feature/<task-name>` for a feature or bug fix, the module's branch `feature/<task-name>-<module>` for a unit). Never create, switch or merge branches, and never commit or push; the driver does that after the session ends.

## Steps

1. Confirm `plan.md` is `Done`. If not, say so and end.
2. **A unit only:** check the approved TDD copy (link in `units.md`) has not changed since the split: its last-modified time in Drive is no later than "TDD copy last modified when split" in `units.md`. If it has changed, ask the person (`Waiting for answers` in `build-log.md`, tag the tech lead) and end.
3. Create `build-log.md` from `${CLAUDE_PLUGIN_ROOT}/templates/build-log.md`.
4. Start the `aidlc:test-writer` agent with the paths to `clarify.md` and `plan.md` and the test files named in the plan. It writes the tests. Run them: they should fail, because the code doesn't exist yet. Note in the log any test that passes already, and why.
5. Copy the TODO list from `plan.md` into `build-log.md` (`plan.md` is `Done`, so it can't be edited). Do each TODO in order and tick it in `build-log.md`.
6. Log in `build-log.md`: every change from the plan (what, why, and whether it affects a "done" item or shared decision), and every problem met.
7. If a change affects a "done" item or a shared decision: go back to Plan (rules: Going back): add `Go back to: plan.md` and the reason to `build-log.md`, set it to `Waiting for go-back approval`, and end.
8. Run the tests and the project's existing test suite.
9. Gate: every TODO is complete and every change is logged. Set `build-log.md` to `Status: Done` and end. The driver commits, pushes, and starts Check.

## Coming back from a failed Check

`build-log.md` is `Stale` because Check found the code did not match the plan.

1. Read the failure, evidence and cause in `check-assessment.md`.
2. Set `build-log.md` to `Draft`. Add an "Attempt <n>" row (which failure, what you fixed) and a "Revisions" note.
3. If two attempts at this same failure are already logged, don't try again: set `Waiting for answers`, explain the two attempts and why the cause is probably in an earlier step, and end.
4. Fix only that failure. Run the tests and the suite.
5. Set `build-log.md` to `Done` and end. The driver runs Check again.

## Never

- Write code before `plan.md` is `Done` (a hook blocks it anyway).
- Change a test to make it pass.
- Make a design decision the plan didn't make.
- Commit, push, or change branches.
