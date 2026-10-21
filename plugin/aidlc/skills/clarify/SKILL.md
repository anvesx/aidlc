---
name: clarify
description: The AIDLC Clarify step. Turns a need into a clear, checkable statement of what is wanted and what "done" means. A project or new module writes the PRD as a Google Doc (in Cowork); a feature, a bug fix and each unit write clarify.md (in a driver session in Claude Code). Use when AIDLC work is at the Clarify step.
---

# Clarify

**Job:** make sure the right thing gets built. Say **what** and **why**, never **how** (that is Plan). Clarify only clarifies: it never judges how big the work is.

Before starting: read `${CLAUDE_PLUGIN_ROOT}/skills/aidlc/rules.md` if you haven't this session. Load the `aidlc:asking-questions` and `aidlc:test-design` skills. For a bug, also load `aidlc:root-cause`.

## Expertise: what good Clarify output looks like

- **One meaning per requirement.** If two people could read it two ways, it is not done. Rewrite it or ask.
- **Every "done" item is a yes/no check** that someone could test without asking you what you meant. "Fast" is not a check; "loads in under 2 seconds on the product page" is.
- **Behaviors, not tasks.** Write "A shopper can remove an item from the cart", not "Update cart.js".
- **Scope out is written down.** Anything a reader might assume is included, but isn't, goes under "Out".
- **Nothing is invented.** Every requirement comes from the person's input. If you had to fill a gap, it goes under Assumptions (to be confirmed) or Questions, never silently into a requirement.
- **Gaps are found, not guessed.** For each requirement ask: who does it, what triggers it, what they see after, what happens when it goes wrong, what the limits are. A missing answer is a question.

## clarify.md (driver session)

The driver created `clarify.md` with the `Claimed by:` line and the request (or the unit's row) in "Source". It is the first stage of a feature, a bug fix or a unit. Each run of this stage is one round.

1. **First round:** fill in the type, the four questions and the deep steps (rules: How deep each step goes; for a unit, copy them from its row in `units.md`). Set `Approval needed: yes` if Clarify is deep, otherwise `no`.
2. Write the need for the type:
   - **Unit:** point to its row in `units.md`, the PRD IDs and TDD decisions it covers (approved copies linked at the top of `units.md`). Copy its behavior and "done" list. Do not rewrite the need; it was approved. Read the PRD and TDD copies only for the parts this unit covers.
   - **New:** the need in 1 to 2 lines (light), or the full need with scope in and out (deep).
   - **Change:** start the `aidlc:code-reader` agent to describe how the affected part works now. Then write how it should work.
   - **Bug:** follow the `aidlc:root-cause` skill: steps to reproduce, what happens, what should happen, then the cause. If you can't reproduce it, ask the person.
   - If "Source" is a ClickUp link, read the task in full with the ClickUp connector.
3. Write the "done" list with the `aidlc:test-design` skill: yes/no checks, covering the edge cases that apply.
4. **Later rounds:** the person's answers are in the "Questions and answers" table. Apply each one to the need, scope and "done" list.
5. Collect every blocking gap. If there are any: write them all into the "Questions and answers" table (each with options and your suggested answer), then follow rules: When a stage needs a person (`Waiting for answers`, end).
6. Nothing blocking left: start the `aidlc:checker` agent on `clarify.md` against the original need (the request or ticket, or the unit's row in `units.md`). Fix what it finds with evidence. Repeat up to 2 times; if it still fails, ask the person what remains (`Waiting for answers`).
7. Gate (rules): if `Approval needed: yes`, set `Status: Waiting for approval`, put a short summary for the person under the title, and end. Otherwise set `Status: Done` and end. The driver starts Plan.

## Project or new module in Cowork: the PRD

This runs with the person in the session (the PM, or whoever owns the need).

1. Write the PRD as markdown from `${CLAUDE_PLUGIN_ROOT}/templates/prd.md` in a work file. Requirements get IDs (R1, R2, ...) grouped by area. **IDs are never renumbered**; a removed requirement keeps its ID marked "Removed".
2. Fill section 9 (Risk) with your suggested answers to the four questions, for the whole.
3. Ask the person all open questions in one message. Write answers into section 8. Repeat until nothing blocking is open. Anything you assumed goes in section 7 for them to confirm.
4. Start the `aidlc:checker` agent: the PRD against all of the person's input (every point covered or out of scope, nothing invented, one meaning each, "done when" testable, nothing contradicts). Fix, up to 2 rounds.
5. Create the Google Doc titled `<task-name> PRD` in the work's Drive folder with the `aidlc:google-document` skill. Set its Status to `Waiting for approval`.
6. Tell the person: "Please read the PRD. If it's right, the PM fills in the Approval section themselves (name and today's date) in the Google Doc, then tells me." **Never fill in the Approval section yourself.**
7. When they say it's approved: read the doc and confirm the Approval section is filled in with a name and date. Then make the approval copy: copy the doc with the Drive connector into the same folder, titled `<task-name> PRD v<n> approved` (n counts up from 1). Tell the person not to edit the copy. Set the working doc's Status to `Approved`.
8. Next: the `aidlc:plan` skill (TDD), in the same Cowork session or a new one.

**Changing an approved PRD:** edit the working doc, list the change in section 10 (Decisions) with its reason, get it approved again the same way, and make the next copy (`v2`). If a TDD or `units.md` already exists, tell the person which parts are affected; they must be dealt with before more work is built on them.

## Never

- Write how it will be built.
- Judge the size of the work, or ask the person about it.
- Fill a gap without marking it as an assumption or a question.
- Fill in or change an approval.
