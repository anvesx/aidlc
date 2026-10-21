---
name: plan
description: The AIDLC Plan step. Decides how the work will be built, without breaking what exists. A project or new module writes the TDD (modules and shared decisions, no units) as a Google Doc (in Cowork); a feature, a bug fix and each unit write plan.md with TODOs (in a driver session in Claude Code). Use when AIDLC work is at the Plan step.
---

# Plan

**Job:** decide how to build it without breaking what already exists. The need was settled in Clarify; don't change it here. If the need looks wrong, go back (rules: Going back).

Before starting: read `${CLAUDE_PLUGIN_ROOT}/skills/aidlc/rules.md` if you haven't this session. Load `aidlc:asking-questions`.

## Expertise: what good Plan output looks like

- **Read before deciding.** Every statement about existing code ends with `Checked: <file>` or `Assumed: <why>`. Never describe code from memory or guesses. Use the `aidlc:code-reader` agent so the reading doesn't fill this session.
- **Real options, real reasons.** For each choice that matters, name the options you considered and why you picked one. "It's the standard way" is not a reason; "the cart already uses this pattern in cart-drawer.js, so it stays consistent" is.
- **Follow what's already decided.** Read the decisions and standards for this area first (through `aidlc/index.md`). Anything the PRD, TDD or ticket names (a tool, an approach) is followed. If it can't work, raise it; never pick something else quietly.
- **Shared or local.** A choice belongs in the TDD only if more than one module or unit depends on it, or it is hard to change later (data structure, how parts talk, outside services, shared components). Everything else is left to the unit's own plan.
- **Name what could break.** For every part you change, ask what else uses it.
- **Prefer the smallest change that meets every "done" item.**

## plan.md (driver session)

1. Create `plan.md` from `${CLAUDE_PLUGIN_ROOT}/templates/plan.md` (first round only). `Approval needed: yes` if Plan is deep (from `clarify.md`).
2. Read `clarify.md`. For a unit, also the shared decisions in `units.md` and the parts of the approved TDD copy it must follow.
3. **Light:** a few TODOs. Each says what changes, where, and which "done" item it serves.
   **Deep:** first start the `aidlc:code-reader` agent on the parts this touches and put its summary in the file. Then list every part that changes and what could break, give the reason for each key choice, then the TODOs.
4. Name the tests the `aidlc:test-writer` agent will write (which "done" items, which files), so Build can start with them.
5. Questions for the person: write them all into the "Questions and answers" table, with options and your suggested answer, and follow rules: When a stage needs a person (`Waiting for answers`, end). In a later round, apply their answers.
6. Start the `aidlc:checker` agent: `plan.md` against `clarify.md` (every "done" item has a TODO, nothing extra, nothing contradicts a recorded decision). Fix, up to 2 rounds.
7. Gate: `Approval needed: yes` means set `Status: Waiting for approval`, put a short summary for the person under the title, and end. Otherwise set `Status: Done` and end. The driver starts Build.

## Project or new module in Cowork: the TDD

This runs with the tech lead in the session.

1. Read the **approved PRD copy** (`<task-name> PRD v<n> approved`), never the working doc.
2. **Starting point.** New project: list what is being set up from scratch (language, framework, structure, hosting); each is a shared decision. Existing code: it must be reachable (a connected folder in Cowork, or the GitHub repo). If you can't reach it, ask; never guess what the code does. Either way, list outside services and systems it must work with.
3. Write the TDD as markdown from `${CLAUDE_PLUGIN_ROOT}/templates/tdd.md` in a work file:
   - Shared decisions with options, reasons, and whether each is hard to undo.
   - What could break and how it would be undone.
   - **Modules:** split by working behavior, not by technical layer. Each lists the PRD IDs it covers and which module it depends on. **No units:** the split into phases and units happens later, in the repository, in `units.md`.
   - **Coverage check:** every PRD requirement ID is in exactly one module.
   - How the whole will be checked against the PRD.
4. Ask the tech lead all questions and choices in one message, each choice with options and your recommendation. Write answers in. Repeat until nothing blocking is open.
5. Start the `aidlc:checker` agent: the TDD against the approved PRD (every requirement mapped to a module, nothing the PRD names ignored, nothing invented, every code statement marked Checked or Assumed, the coverage check true). Fix, up to 2 rounds.
6. Create the Google Doc `<task-name> TDD` in the work's Drive folder with the `aidlc:google-document` skill. Put the approved PRD copy's link at the top. Set Status to `Waiting for approval`.
7. Tell the tech lead to read it and fill in the Approval section themselves (name and date), then tell you. **Never fill it in yourself.**
8. When approved: confirm the Approval section is filled in, make the copy `<task-name> TDD v<n> approved` in the same folder, and set the working doc's Status to `Approved`.
9. Tell the person: "The TDD is approved. Open the project's repository in Claude Code and run /aidlc:start; it gives you the driver command, with this copy's link. The driver writes units.md there, and the tech lead approves it."

**Changing an approved TDD:** add the change to section 9 (Decision log) with the modules and units it affects, get it approved again, and make the next copy. If `units.md` already exists, tell the tech lead: AIDLC has no defined path yet for updating `units.md`, its tickets and open branches after a TDD change. They decide what happens.

## Never

- Change the need. Go back to Clarify instead.
- Describe existing code without having read it.
- Put units in the TDD.
- Fill in or change an approval.
