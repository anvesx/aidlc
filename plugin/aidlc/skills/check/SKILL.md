---
name: check
description: The AIDLC Check step. The checker agent confirms every "done" item passes with evidence and nothing else broke. Three kinds - the inner check of a feature, bug fix or unit (check-assessment.md), the phase check of a project or new module (phase-check.md, approved by a developer who built the phase), and the final check of the whole (check-assessment.md, approved by QA). On a failure, finds which step the cause is in. Use when AIDLC work is at a Check step.
---

# Check

**Job:** confirm the work matches "done" and nothing else broke. The maker never checks its own work: the `aidlc:checker` agent does, in a fresh context.

Before starting: read `${CLAUDE_PLUGIN_ROOT}/skills/aidlc/rules.md` if you haven't this session. Load `aidlc:test-design`. On a failure, load `aidlc:root-cause`.

## Expertise

- **Evidence or it didn't pass.** Each item gets a result and the evidence: the test name and its output, a command and what it printed, or a screenshot path. "Looks right" is not evidence.
- **Check against the step before**, not against what the code happens to do.
- **Nothing else broke.** Run the project's whole test suite, and check the parts the plan said could break.
- **A flaky test is a failure** until its cause is found.
- **Report exactly.** Never write PASS for something that failed or didn't run.

**The checker agent can't reach Google Drive.** When it must check against the PRD or TDD, read the approved copies yourself and give it the text it needs in its prompt.

## Inner check (feature, bug fix or unit): `check-assessment.md`

1. Create `check-assessment.md` from `${CLAUDE_PLUGIN_ROOT}/templates/check-assessment.md` (or, if it is `Stale` after a Build attempt, set it to `Draft` and add a "Revisions" note). `Approval needed: yes` if Check is deep (from `clarify.md`).
2. Start the `aidlc:checker` agent with the work folder path. It reads `clarify.md`, `plan.md` and `build-log.md`, runs the tests and the suite, and returns a result with evidence for each "done" item, plus anything else it found broken.
3. Write its results into `check-assessment.md` as they came out.
4. **Deep** also needs: related areas confirmed working, and if the work is hard to undo, a written undo plan.
5. **All pass:** `Approval needed: yes` means set `Status: Waiting for approval`, put a short summary for the person under the title, and end. Otherwise set `Status: Done` and end.
6. **Any fail:** follow "Finding the cause" below.

## Phase check: `phase-check.md`

The driver runs this on the module's branch when every unit in the phase is `Done`. It always needs approval.

1. Create `<module>/phase-<N>-<name>/phase-check.md` from `${CLAUDE_PLUGIN_ROOT}/templates/phase-check.md`.
2. Start the `aidlc:checker` agent with: the approved PRD and TDD copies (links in `units.md`), this phase's rows in `units.md`, the phase's unit folders, and the code on this branch. It checks every PRD ID and TDD decision the phase covers, that the units work together, and runs the whole test suite.
3. Write its results in.
4. **All pass:** set `Status: Waiting for approval`, and end.
5. **Any fail:** write what failed, the evidence, the cause (with `aidlc:root-cause`), which unit and step it is in, and what you propose. Set `Waiting for answers`, and end. They decide.

## Final check of the whole: `check-assessment.md` in the task folder

The driver runs this on `feature/<task-name>-final`, after every module is merged into the target branch. It always needs QA's approval.

1. The driver already created the task folder's `check-assessment.md` with `Approval needed: yes` and a `Claimed by:` line. Fill it in and keep both.
2. Start the `aidlc:checker` agent with the approved PRD and TDD copies (links in `units.md`), the TDD's "How the whole will be checked" section, every `phase-check.md`, and the code. It checks the whole against every PRD requirement, with evidence. Units and phases that each pass can still fail together.
3. **All pass:** `Waiting for approval`, end.
4. **Any fail:** as the phase check: write the failure, evidence, cause and proposal, `Waiting for answers`, tag QA, end.

## Finding the cause (inner check)

Use the `aidlc:root-cause` skill. Then decide where the cause is (rules: Going back):

| Cause | What you do |
|---|---|
| The code doesn't match the plan | Write the failure, evidence and cause in `check-assessment.md`. If `build-log.md` already logs 2 attempts at this same failure, set `Waiting for answers` instead and ask the person. Otherwise mark `build-log.md` `Stale`, then `check-assessment.md` `Stale`, and end. The next session redoes Build. |
| The plan doesn't work | In `check-assessment.md`, add `Go back to: plan.md` and a "Why go back" section, set it to `Waiting for go-back approval`, and end. |
| The need or "done" list was wrong | Same, with `Go back to: clarify.md`. |
| A TDD shared decision was wrong | `Waiting for answers`: say the TDD must change in Cowork through its decision log, and which units are affected. Tag the tech lead. |
| The PRD was wrong | `Waiting for answers`: say the PRD must change in Cowork. Tag the PM. |

Always say in plain words what failed, the evidence, where you think the cause is, and what you propose.

## Never

- Check your own work in this session. Always use the `aidlc:checker` agent.
- Write PASS without evidence.
- Change a test to make it pass.
