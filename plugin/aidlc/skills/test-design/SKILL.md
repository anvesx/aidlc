---
name: test-design
description: How AIDLC designs tests - from the spec (clarify.md, plan.md, the PRD), never from the code, with every "done" item turned into yes/no checks and run through a fixed list of edge cases. Use when writing a "done" list in Clarify, when the test-writer agent writes tests, and in the Check step.
---

# Test design

## The rule

Tests come from **what was asked for** (the "done" list, the plan, the PRD), never from the code. A test written by reading the code checks that the code does what the code does, which catches nothing.

## A good "done" item

- Is a **yes/no** question someone else could answer without asking you.
- Names **who**, **what action**, and **what they should see**.
- Has a **number** where "fast", "many", "large" would be vague.

| Weak | Strong |
|---|---|
| Cart works well | A shopper can remove an item, and the total updates without a page reload |
| Handles errors | If the stock API doesn't answer within 5 seconds, the page shows "Stock unavailable" and the Add button is disabled |

## Edge cases: go through every one, for every "done" item

For each item, either write a check for the case or mark it "not applicable: <reason>".

1. **Empty:** no input, empty list, nothing found.
2. **Limits:** the smallest and largest allowed values, and one past each.
3. **Wrong input:** wrong type, wrong format, special characters, very long text.
4. **Permissions:** someone not allowed tries it; someone logged out tries it.
5. **The same action twice:** double click, resubmit, retry after a failure.
6. **Order and timing:** steps out of order, two people at once, a slow response.
7. **Outside systems fail:** an API is down, slow, or returns something unexpected.
8. **State left behind:** after a failure, is anything half-saved?
9. **What should not change:** the existing behavior around the change still works.

For a bug: the first test reproduces the bug and fails before the fix.

## Writing the test code (test-writer agent)

- One test per check, named after the "done" item it proves.
- Use the project's existing test setup and style. If the project has no tests, say so in your report instead of inventing a setup; the person decides.
- Tests must fail before the code exists, for the right reason.

## Running checks (Check step)

- Record each result with its evidence: test name and output, or the command and what it printed.
- A test that sometimes passes and sometimes fails counts as a failure until the cause is found.
