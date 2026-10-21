# PRD: <name>

| Field | Value |
|---|---|
| Owner | <person who approves> |
| Status | Draft / Waiting for approval / Approved |
| Date | <date> |
| Task | <task-name> |
| Parent | <link to the parent PRD, only if this is a sub-PRD> |

## 1. Problem
What is wrong or missing today, for whom, and how we know.

## 2. Goal
What will be different when this is done. How we will tell (a number, if one exists).

## 3. Users
Who uses this, and what each type of user needs from it.

## 4. Scope
**In:** what this covers.

**Out:** what this does not cover, stated explicitly.

## 5. Requirements
Grouped by area or module. Each is a behavior: "A <user> can ...". IDs are never renumbered; a removed requirement keeps its ID, marked "Removed".

### <Area or module name>

| ID | Requirement | Done when (yes/no checks) | Source |
|---|---|---|---|
| R1 | A user can ... | ... ; ... | <link, "Person", or "AI guess"> |

## 6. Constraints
Fixed limits we cannot change: deadline, tech that must be used, existing systems, legal, budget.

## 7. Assumptions
Things treated as true without proof. Each must be confirmed or removed before approval.

| # | Assumption | Confirmed by / date |
|---|---|---|

## 8. Open questions
Must be empty, or each item explicitly deferred, before approval.

| # | Question | What it affects | Who answers | Answer |
|---|---|---|---|---|

## 9. Risk (the four questions, for the whole)

| Question | Answer | Reason |
|---|---|---|
| Is it clear what is wanted? | | |
| Unfamiliar area, or many parts touched? | | |
| Hard to undo? | | |
| Who is affected, and how soon would we notice? | | |

## 10. Decisions
Decisions made while writing this PRD, and changes after approval.

| ID | Decision | Why | Date |
|---|---|---|---|

## 11. Approval
Filled in by the approver only, never by the AI.

Approved by: <name>   Date: <date>
