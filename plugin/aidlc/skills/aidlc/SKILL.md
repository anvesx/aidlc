---
name: aidlc
description: Start or continue AIDLC work (devx's AI-driven development lifecycle). Use when a person asks to start, continue or check work through AIDLC, names a ClickUp task or a piece of work to run through AIDLC, runs /aidlc:start, or asks where AIDLC work stands. Sets up the repository, or starts the driver for the work and gives the AIDLC page link; in a driver session, runs the one stage the driver names.
---

# AIDLC: start or continue

First read `${CLAUDE_PLUGIN_ROOT}/skills/aidlc/rules.md`. It is the rulebook every step follows. The session-start message gives the plugin folder and the exact driver command.

Never ask a person about the process (how big the work is, how deep a step goes). Keep them informed in a line or two.

## Which situation is this?

1. **Cowork** (you have Google Drive and Docs tools and are not inside a project's repository): section "Cowork".
2. **Driver session** (the session-start message says "This is a driver session"; the driver sets the environment variable `AIDLC_DRIVER` to `1`): section "Driver session".
3. **A person's own session in Claude Code**: section "A person's session".

## Driver session

The driver names one stage file in the arguments (for example `aidlc/work/cart-fix/plan.md`). Run that one stage, then end.

1. Read `aidlc/index.md`, `aidlc/project.md`, and the files before this stage in its folder.
2. Check the file: if its status is any `Waiting ...` or `Done`, there is nothing to do; say so in one line and end. (`units.md` at `Approved` still has work: its tickets.)
3. Run the skill for that file:

| File | Skill |
|---|---|
| `clarify.md` | `aidlc:clarify` |
| `plan.md` | `aidlc:plan` |
| `build-log.md` | `aidlc:build` |
| `check-assessment.md` | `aidlc:check` (the final check if its folder has `units.md`, otherwise inner) |
| `phase-check.md` | `aidlc:check` (phase check) |
| `learnings.md` | `aidlc:record` (for the whole if its folder has `units.md`) |
| `units.md` | `aidlc:units` |
| `pr.md`, `pr-units.md`, `pr-final.md` | `aidlc:pr` |

4. End when that stage is `Done`, or waits on a person (rules: When a stage needs a person). Never start the next stage. Never run `git commit`, `git push`, `git switch` or `git checkout`; the driver does all git work.

## A person's session

### First time: set up the repository

If there is no `aidlc/project.md` at the repository root (the `aidlc/` folder may be missing or empty):

1. Create `aidlc/` from the templates in `${CLAUDE_PLUGIN_ROOT}/templates/`: `index.md`, `project.md`, and empty `standards/`, `decisions/` and `work/` folders (a `.gitkeep` in each).
2. Fill in `project.md` by reading the repository (README, package files, how to run and test). Mark anything you could not confirm under "Assumed".
3. Ask the person, all in one round, using the question tool (AskUserQuestion) so they can pick or type each answer: the target branch, the project's Slack channel ID, the ClickUp list for phase tickets, and the team (for each person: name, git email, Slack user ID, role: PM, Tech lead, Developer or QA).
   - **Never guess or suggest a value.** Where the repository shows the real choices (for example its branches), list them as options without recommending one.
   - Check each git email they give against `git config user.email`; if they differ, ask which one their commits use.
   - If they don't know an answer yet, write `<not yet decided>` and tell them what it blocks (the driver can't start without the target branch).
   - Write the answers into `project.md`, and remove anything under "Assumed" that their answers settled.
4. Add `CLAUDE.md` at the repository root from `${CLAUDE_PLUGIN_ROOT}/templates/claude-md.md` (or add its line to the existing `CLAUDE.md`).
5. Create `.claude/settings.json` with the file tools (not a shell command) from `${CLAUDE_PLUGIN_ROOT}/templates/settings.json` (if one exists, merge: keep what is there, add AIDLC's entries). Add the project's own test command to `permissions.allow` (for example `Bash(npm test:*)`), so driver sessions can run tests. Show the person what you added.
6. Tell the person:
   - Review these files and commit them yourself, for example: `git switch -c feature/aidlc-setup && git add aidlc CLAUDE.md .claude/settings.json && git commit -m "AIDLC: set up" && git push -u origin feature/aidlc-setup`, then merge it into the target branch through a PR.
   - **Every person on the team must open Claude Code in this repository once and accept the trust dialog.** Without that, the shared settings don't apply and driver sessions can't run tools.

### Every other time

0. **Is the driver already running in this folder?** Read `.git/aidlc-driver.json` (`git rev-parse --absolute-git-dir` gives the folder). If it exists and its `pid` is alive (`kill -0 <pid>`), the work is running: tell the person, give them its page link (`url`), and remind them that answers and approvals go on that page. Don't start another driver, don't switch branches and don't change files here. Stop.
1. **New work, or continuing work: start the driver.** Work is run by the driver, never in this session.
   1. Check `aidlc/project.md` has a target branch. If it says `<not yet decided>`, ask for it (question tool) and write it in first.
   2. Work out what to run:
      - A new feature or bug fix: the request is what the person asked for. Suggest a task name (short, lowercase, words joined by `-`).
      - A project or new module whose TDD is approved in Cowork: the approved TDD copy link (ask for it if you don't have it).
      - Existing work (to continue it, or for a second person to take another module of a project): its task name.
   3. Ask once with the question tool, in one question: the task name you suggest, and "AI will commit and push to this work's own branches (feature/...), never to the target branch. Start?" Only a yes starts it.
   4. Start it in the background of this window, using the plugin folder from the session-start message:
      `nohup python3 "<plugin>/scripts/aidlc_driver.py" <task-name> "<request>" --approved --watch-pid "$PPID" > "$(git rev-parse --absolute-git-dir)/aidlc-driver.log" 2>&1 &`
      (for a project or new module use `--tdd "<link>"` instead of the request; to continue, give only the task name). `--watch-pid` ties the work to this Claude Code window.
   5. Wait a few seconds, then read `aidlc-driver.log` in the same folder. Give the person the link on the line starting `AIDLC page:`. If the log shows the driver stopped instead (for example uncommitted changes), tell them exactly what it says.
   6. Tell them, briefly:
      - the work runs while this window stays open, and closing it stops the work (a step that is running is thrown away and redone next time);
      - everything happens on the page: what's running, questions, approvals; a Slack DM with the link comes when something needs them;
      - don't edit files in this repository folder while the work runs (the driver switches branches and commits here); use a separate copy for other work.
2. **No driver running, and something waits on this person** (for example a tech lead or QA approving a project step in their own session):
   - If they named a branch or task, get on it: if `git status --porcelain` shows uncommitted changes, stop and tell them; otherwise `git fetch`, `git switch <branch>`, `git pull --ff-only`.
   - Read the status lines under `aidlc/work/` and show what is `Waiting for answers`, `Waiting for approval` or `Waiting for go-back approval`, and who it waits on (rules: Who to tag). Their git email is `git config user.email`.
   - **Answers:** show the questions with options and suggested answers (`aidlc:asking-questions`), take their answers, write each into the file, and set the file to `Draft`. The stop hook commits and pushes them under their name.
   - **Approval or go-back:** summarize what is waiting, and tell them to run `/aidlc:approve` (with part of the path if more than one waits). Never approve for them. If they say no: write their reasons into the file (a `## Not approved` note) and set it to `Draft`.
   - If nothing is waiting and they just got a Slack message, the driver may not have pushed yet: ask them to try again in a minute.

## Cowork

You can only write the PRD and the TDD here.

1. Ask the person which project folder in Drive and which work (a ClickUp task or a short task name).
2. Find or create the work's Drive folder `<task-name>` inside the project's folder.
3. No approved PRD: run the `aidlc:clarify` skill (PRD).
4. PRD approved but no approved TDD: run the `aidlc:plan` skill (TDD).
5. Both approved: tell the person: "The rest runs in the repository. Open it in Claude Code and run /aidlc:start; it gives you the driver command." The tech lead approves the split into units there.

## Never

- Approve anything, or write an `Approved by:` line.
- Skip a step or a gate.
- Run a stage in a person's own session.
- Ask the person to do work you can do.
