# AIDLC rules (shared by every step)

Read this once per session before doing any step. Every step skill follows it.

## The one principle

The AI does all the work. A person only makes decisions: answers questions, approves, confirms going back to an earlier step, and merges PRs. Never ask a person to do work you can do. Never ask a person about the process itself (how big the work is, how deep a step goes).

## Who runs what

- **The driver** runs the work. `/aidlc:start` starts it in the background of the person's Claude Code window and gives them the link to the **AIDLC page** (on their laptop). It starts one fresh headless session per stage, waits, and repeats. The page shows every step, what the running session is doing, and what each step wrote; the person answers and approves there, and the driver continues at once. It stops when that Claude Code window closes (a running step is thrown away and redone next time). It stops when the work is complete, or when the same stage runs twice without its status changing (it posts in Slack first).
- **A driver session** is a session the driver started. You can tell because the session-start message says "This is a driver session" (the driver sets the environment variable `AIDLC_DRIVER` to `1`). Only driver sessions run stages (Clarify, Plan, Build, Check, Record, units, phase check, final check, PR).
- **A person's own session** never runs a stage. In it, `/aidlc:start` sets up the repository and starts the driver. When no driver is running there (for example a tech lead or QA approving a project step), it also takes answers and points to `/aidlc:approve`.
- **Stage:** one step file in one folder (for example `plan.md` of one unit). One driver session runs exactly one stage, then ends. It knows only what is in the files.
- **Git:** the AI never runs `git commit` or `git push` (the project settings deny it). The driver makes branches, commits, pushes and pulls. The page (through the driver) and the approve hook commit and push approvals, and the page and the stop hook commit and push a person's answers, always under that person's git name. A target branch only changes through a PR that a person merges.

## The loop

Every piece of work runs the same five steps: **Clarify, Plan, Build, Check, Record.**

There are four kinds of work:

| Kind | Starts in | How it runs |
|---|---|---|
| **Project** | Cowork | The PRD (Clarify) and TDD (Plan) are Google Docs. Then, in the repository: `units.md` splits it into modules, phases and units; each unit runs the five steps; each phase gets a phase check; each module gets a PR; the whole gets a final check, learnings and a PR. |
| **New module** | Cowork | The same as a project, with one module in the TDD. |
| **Feature** | Claude Code | One folder, the five steps, then a PR. Type New or Change. |
| **Bug fix** | Claude Code | The same as a feature. Type Bug. |

A person decides the kind by where they start. The AI never judges it.

## How deep each step goes (your call, never a question)

Decide light or deep for Clarify, Plan and Check yourself, with these four questions. Write each answer and a one-line reason in `clarify.md`. **When unsure, go deep.** Ask them again whenever work goes back to an earlier step.

| Question | If the answer is risky |
|---|---|
| 1. Is it unclear what is wanted? | Clarify goes deep |
| 2. Is it in an unfamiliar area, or does it touch many parts? | Plan goes deep |
| 3. Is it hard to undo? | Check goes deep |
| 4. Would a mistake affect many people, or be noticed late? | Check goes deep |

For a unit, `units.md` already says which steps are deep (the tech lead approved it). Use that.

| Step | Light | Deep |
|---|---|---|
| Clarify | The need in 1 to 2 lines, plus a yes/no "done" list | Written need, scope in and out, a yes/no "done" list, assumptions and open questions answered by a person, approval |
| Plan | A few lines: what changes and how, as TODOs | First read and summarize the existing code touched, list everything that changes and what could break, give reasons for key choices, approval |
| Check | Run it and confirm each "done" item | Each "done" item passes with evidence, related areas still work, an undo plan if hard to undo, approval |

A deep step has `Approval needed: yes`. Build has no levels. Record always runs. The checker agent always runs at the Clarify, Plan and Check gates, light or deep. Clarify asks in rounds until nothing blocking is left.

## Types of work (changes where Clarify starts)

A feature is type New or Change; a bug fix is type Bug. A unit of a project or new module takes the type that fits it.

| Type | Clarify starts with | Done means |
|---|---|---|
| New | The need | The "done" list passes |
| Change | How it works now, then how it should work | The new behavior works, and everything that should not change still works |
| Bug | Steps to reproduce it, then the real cause (use the root-cause skill) | The cause is fixed, the symptom is gone, and a test now exists that would have caught it |

If a bug can't be reproduced, ask the person for more information. If a bug fix needs different behavior, it is now a change.

## Files and folders

All AIDLC files in a repository live under `aidlc/`. Folders are named by the task name (short, lowercase, words joined by `-`).

```
aidlc/
  index.md                     the map: standards and decisions
  project.md                   project basics, target branch, Slack, ClickUp list, team
  standards/<topic>.md         rules for how work is done
  decisions/D-NNN-<name>.md
  work/<task-name>/            one folder per piece of work
```

**A feature or bug fix:** `aidlc/work/<task-name>/` holds `clarify.md`, `plan.md`, `build-log.md`, `check-assessment.md`, `learnings.md`, `pr.md`.

**A project or new module:**

```
aidlc/work/<task-name>/
  units.md                     the split (modules, phases, units)
  pr-units.md                  the PR that takes units.md to the target branch
  <module>/
    phase-<N>-<name>/
      U<n>-<name>/             one unit: the five step files
      phase-check.md
    pr.md                      the module's PR
  check-assessment.md          final check of the whole
  learnings.md                 learnings for the whole
  pr-final.md                  the final PR
```

- Templates are in `${CLAUDE_PLUGIN_ROOT}/templates/`. Always start a file from its template.
- The driver may already have created the stage file from its template, with a `Claimed by:` line (it does this for `clarify.md`, `units.md`, `pr-units.md`, and the final `check-assessment.md`, `learnings.md` and `pr-final.md`). Then fill that file in; never recreate it, and never change or remove the `Claimed by:` line (a hook blocks it).
- The PRD and TDD are Google Docs in the project's Drive folder, in a folder named `<task-name>`. The repository holds only links to them.

## Branches

| Work | Branch | Made from | Reaches the target by |
|---|---|---|---|
| A feature or bug fix | `feature/<task-name>` | target | its PR (`pr.md`) |
| units.md | `feature/<task-name>` | target | its own PR (`pr-units.md`), before any module branch is made |
| Module | `feature/<task-name>-<module>` | target, after units.md is merged | its PR (`<module>/pr.md`), after its last phase check is Done |
| Final check | `feature/<task-name>-final` | target, after every module is merged | its PR (`pr-final.md`) |

The target branch is in `project.md`. The driver makes and switches branches; a driver session never does. Units have no branches of their own: a module's units run one after another on the module's branch.

## Status (the state lives in the files)

Every file in `aidlc/work/` has these lines at the top, exactly in this form:

```
Status: Draft
Approval needed: no
```

| Status | Meaning |
|---|---|
| `Draft` | Being worked on, or ready for the next driver session |
| `Waiting for answers` | Needs a person's answers (see "When a stage needs a person") |
| `Waiting for approval` | Finished; needs a person's approval (on the AIDLC page, or `/aidlc:approve`) |
| `Waiting for go-back approval` | You propose going back to an earlier step; needs a person's approval (page or `/aidlc:approve`) |
| `Approved` | `units.md` only: approved, tickets not yet created |
| `Done` | Gate passed (and approved, if approval was needed) |
| `Stale` | Was Done, but an earlier step changed; must be redone |

- The current stage is the first step file that is not `Done`. The driver tells each session which one.
- **You never write an approval line, and never call the AIDLC page's address.** Only a person's click on the page, or their `/aidlc:approve`, records an approval. A hook blocks you if you try.
- **Never change a status through the shell** (`sed`, `echo >>` and so on). Use the file tools, so the guard sees it.
- A file marked `Done` is never edited. To change it, mark it `Stale` (that is the only edit allowed) and redo it.
- `units.md` while `Approved`: only ticket links may be added or changed.
- If a step needs approval, set `Status: Waiting for approval` when it is ready, and end (the driver tells the person). The person's approval (on the page or with `/aidlc:approve`) sets it to `Done` (or `Approved` for `units.md`).
- If no approval is needed, set `Status: Done` yourself once the gate passes.

## When a stage needs a person

A driver session has no person to talk to. When you need a person (answers, an approval, a go-back, PR guidance):

1. Write the request into the file you are working on. For answers: the "Questions and answers" table, or a `## Waiting on a person` section saying what is needed. Each question is clear on its own, with options and your suggested answer (`aidlc:asking-questions`).
2. Set the status: `Waiting for answers`, `Waiting for approval` or `Waiting for go-back approval`.
3. Don't post in Slack yourself. The driver sees the new status and sends the person a Slack DM: the developer who runs the driver gets the link to the AIDLC page; anyone else (for example the tech lead or QA in a project) is told to run `/aidlc:start` in their own session.
4. End the session. The driver commits and pushes, then waits for the status to change.

**Who to tag (and who may approve):**

| File | Person |
|---|---|
| A feature's, bug fix's or unit's files | The developer on the `Claimed by:` line of that folder's `clarify.md` |
| `units.md` | The tech lead |
| `phase-check.md` | The developer who owns the module (who claimed its units) |
| Final `check-assessment.md` | QA |
| `pr.md`, `pr-units.md`, `pr-final.md` | The person who started the driver (their git email is `git config user.email`). PR files only ask for answers; they never need approval. |
| PRD | The PM (in Cowork) |
| TDD | The tech lead (in Cowork) |

A go-back is approved by the same person who approves that file. The approve hook checks the approver against the team table in `project.md`; anyone else is refused.

**On the AIDLC page** the person answers, approves or says no with a reason; the driver records it under their git name and carries on. **In a person's own session without a driver** (`/aidlc:start`): show what is waiting, take their answers, write them into the file, and set the status back to `Draft`. If they don't approve something waiting for approval (or a go-back), write their reasons into the file the same way and set it back to `Draft`; the driver redoes the stage. The stop hook commits and pushes the change under their name. Never run the stage itself.

## Gates (a step moves forward only when its gate passes)

| Step | Gate |
|---|---|
| Clarify | A "done" list exists; no open questions; the checker agent passed it against the need; approved if deep |
| Plan | Every TODO links to a "done" item; the checker agent passed it against Clarify; approved if deep |
| Build | Every TODO is complete; every change from the plan is in `build-log.md` |
| Check | Every "done" item passes with evidence, judged by the checker agent; approved if deep |
| Record | `learnings.md` written; anything that matters beyond this work promoted (a unit only lists it under "To promote") |
| units.md | Every PRD ID in exactly one unit; every unit passes the small-enough test; checker passed; tech lead approved; tickets linked |
| Phase check | Every unit in the phase Done; the phase checked against the PRD and TDD with evidence; approved by a developer who built it |
| Final check | Every phase check Done and every module merged; the whole checked against the PRD and TDD with evidence; approved by QA |
| PR | The person gave guidance and confirmed; the PR is open and linked in the file |

Project or new module: PRD approved before the TDD starts; TDD approved before `units.md`; `units.md` merged before any module branch.

## Splitting a project or new module (units.md)

The TDD has modules and shared decisions, no units. `units.md` splits each module into sequential phases, and each phase into units.

**A unit is small enough** only if all four are true:

1. Its "done" fits in a short yes/no list.
2. It can be built and checked in one session.
3. A person can review the result in one sitting.
4. It can be checked on its own, without waiting for other work.

- A unit delivers a visible behavior, and traces to at least one PRD ID or TDD decision. Every PRD ID is in exactly one unit.
- A module's phases run in order, and so do the units inside each phase (in the order of `units.md`), one at a time on the module's branch. A unit depends only on earlier units in the same module.
- **Parallel work happens across modules, never inside one.** Two people each run a driver on a different module. To speed up a big module, split it into more modules in the TDD.
- A module can depend on another module, which must be merged into the target branch first.
- Module names are unique within the work and are never `final`.

**Claim before work:** the driver claims each unit by writing a `Claimed by:` line into its `clarify.md` and pushing it to the module branch before any work starts. The person who claimed a module's first unit owns that module: only their driver runs it. If two drivers try to start the same module, the second push fails and that driver moves on to another module. A feature or bug fix is claimed the same way, and so are the stages at the level of the whole work (`units.md`, `pr-units.md`, and the final steps): only the driver that claimed a stage runs it.

**Shared files in a project or new module:** units never edit `aidlc/index.md`, `aidlc/decisions/`, `aidlc/standards/` or `aidlc/project.md`. Each unit lists what should go there in its own `learnings.md` ("To promote"). The Record of the whole work, at the end, promotes them all at once, so no two branches change the same shared file.

## Going back (to where the cause is, not where the failure showed up)

| What failed | Go back to | Who decides |
|---|---|---|
| The code does not match the plan | Build | You, automatically (at most 2 attempts) |
| The plan does not work | Plan | The person confirms |
| The need or the "done" list was wrong | Clarify | The person confirms |
| A shared decision in the TDD was wrong | The TDD, through its decision log | The person, always |
| The PRD was wrong | The PRD | The person, always |

**Back to Build:** in `check-assessment.md`, write the failure, the evidence and the cause. Mark `build-log.md` `Stale` and then `check-assessment.md` `Stale`, and end. The next session redoes Build (reading `check-assessment.md`), then Check again. If the same failure is still there after 2 attempts (counted in `build-log.md`), do not go back again: set `Waiting for answers`, explain, and ask the person.

**Back to Plan or Clarify** (in the same folder):

1. In the file you are working on, add a line `Go back to: plan.md` (or `clarify.md`) and a short "Why go back" section with the evidence.
2. Set its status to `Waiting for go-back approval`, and end.
3. When the person runs `/aidlc:approve`, the hook marks that step file and every later one `Stale`. If the person says no (they answer instead), set your file back to `Draft` and follow their direction.

**A phase check or the final check fails:** write what failed, the evidence, the cause, and what you propose, set `Waiting for answers`, and end. The person decides.

**The TDD or PRD was wrong:** set `Waiting for answers` and say so. The TDD or PRD changes in Cowork; the work that depends on it waits.

When redoing a `Stale` step, read the "Why go back" section (or the failure in `check-assessment.md`) first, set the file to `Draft`, and add a "Revisions" section saying what changed and why. Files are never deleted.

## Build may find the plan doesn't quite work

- If the change affects no "done" item and no shared decision: log it in `build-log.md` and carry on.
- Otherwise: go back to Plan. Never quietly work around the plan.

## Context

- Every session reads `aidlc/index.md` and `aidlc/project.md`.
- Read the standards for the files you touch, and the decisions for the area you work in (found through `index.md`).
- Do not write down what the code already says clearly.
- If the context and the code disagree, ask the person (Waiting for answers). Do not quietly pick one.
- Never invent a fact, a check result, an answer or a source. If you don't know, look it up or ask.
