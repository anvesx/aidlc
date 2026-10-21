# TDD: <name>

| Field | Value |
|---|---|
| Owner | <person who approves> |
| Status | Draft / Waiting for approval / Approved |
| Date | <date> |
| Task | <task-name> |
| PRD | <link to the approved PRD copy> |

## 1. Approach in short
How the whole thing will work, in a few plain sentences.

## 2. Starting point
Type: New / Existing

**If existing:** what this work touches, written after reading the code.

| Area / file / system | How it works now | Checked or Assumed | Must not change? |
|---|---|---|---|

**If new:** what is being set up from scratch (language, framework, structure, hosting). Each choice goes into section 4.

**Either way:** anything outside this project it must work with (outside services, APIs, designs, accounts). "None" if nothing.

## 3. Approach in detail
The parts involved and how they connect.

## 4. Shared decisions
Only choices more than one module or unit depends on, or that are hard to change.

| ID | Decision | Options considered | Why this one | Hard to undo? |
|---|---|---|---|---|
| SD1 | | | | |

## 5. What could break

| Risk | Where | How we will catch it | How we undo it (if hard to undo) |
|---|---|---|---|

## 6. Modules
Split by working behavior, not by technical layer. Each module gets one branch and one PR. No units here: after this TDD is approved, `units.md` in the repository splits each module into phases and units.

| Module | What it delivers | PRD IDs covered | Depends on module |
|---|---|---|---|
| <module> | | R1, R2 | none |

**Coverage check:** every PRD requirement ID appears in exactly one module. Yes / No

## 7. How the whole will be checked
How we confirm the finished whole meets the PRD's "done", beyond each unit passing on its own.

## 8. Open questions
Must be empty, or each item explicitly deferred, before approval.

| # | Question | What it affects | Who answers | Answer |
|---|---|---|---|---|

## 9. Decision log (after approval)
Each change lists the modules and units it affects, so they get flagged.

| ID | Change | Why | Modules and units affected | Date |
|---|---|---|---|---|

## 10. Approval
Filled in by the approver only, never by the AI.

Approved by: <name>   Date: <date>
