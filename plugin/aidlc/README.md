# AIDLC plugin

devx's AI-driven development lifecycle, for Claude Code and Cowork. **The AI does the work. People make the decisions.**

Every piece of work runs one loop: **Clarify, Plan, Build, Check, Record.**

- **Feature or bug fix** (started in Claude Code): one folder `aidlc/work/<task-name>/`, the five steps, then a PR. Branch `feature/<task-name>`.
- **Project or new module** (started in Cowork; a new module is a project with one module in the TDD): the PRD and TDD are Google Docs written in Cowork. Then, in the repository: `units.md` splits each TDD module into phases and units (approved by the tech lead), each module runs on its own branch with its units one after another (parallel work is across modules), each phase gets a phase check, each module gets a PR, and the whole gets a final check (approved by QA) and a PR.

**The driver runs the work, and the AIDLC page shows it.** Run `/aidlc:start` with what you want done. It starts the driver in the background of your Claude Code window and gives you a link to the AIDLC page on your laptop. The driver runs one fresh headless Claude session per stage and does all the git work. The page shows every step, what the running session is doing right now, and what each step wrote. When something needs you, a Slack DM brings you to the page, where you answer, approve or say no with a reason, and the work carries on at once. Keep the window open while the work runs: closing it stops the work.

## What's in it

| Type | Name | Job |
|---|---|---|
| Command | `/aidlc:start` | Sets up the repository, or starts the driver and gives you the AIDLC page link. In a driver session, runs the one stage the driver names |
| Command | `/aidlc:approve` | Approve a step, or a proposed go-back (only the right person, checked against `project.md`) |
| Script | `scripts/aidlc_driver.py` | The driver |
| Script | `scripts/aidlc_page.py` | Serves the AIDLC page and records answers and approvals from it |
| Page | `page/index.html` | The AIDLC page itself |
| Skill | `aidlc` | Finds the situation and hands over to the right step. `rules.md` is the shared rulebook |
| Skill | `clarify`, `plan`, `build`, `check`, `record` | One per step |
| Skill | `units` | Splits a project or new module into `units.md`, gets it approved, creates ClickUp tickets |
| Skill | `pr` | Prepares a PR, asks the person, opens it on confirmation |
| Skill | `asking-questions`, `test-design`, `root-cause` | Expertise used by more than one step |
| Skill | `google-document` | The devx document style, for the PRD and TDD |
| Agent | `checker` | Checks each output against the step before, with evidence. Never edits |
| Agent | `code-reader` | Reads existing code and returns a short summary |
| Agent | `test-writer` | Writes tests from the spec before the code exists |
| Hook | Session start | Loads `aidlc/index.md`, `aidlc/project.md`, open work, the plugin folder and driver command |
| Hook | Guard | Blocks AI approvals, code edits without a finished plan, edits to Done files and active decisions, setting Approved, changing anything but links in an Approved `units.md`, and changing a `Claimed by:` line |
| Hook | Approve | On `/aidlc:approve`: pulls, checks the approver's role, records the approval, commits and pushes |
| Hook | Stop | Makes sure every work file has a valid status; in a person's own session on a `feature/` branch, commits and pushes their answers |

`templates/` holds every file AIDLC writes, plus `settings.json`, the draft for the project's shared `.claude/settings.json` (what driver sessions may do without asking).

## Install

**Claude Code:** see the repository README (`/plugin marketplace add devx-commerce/rnd-aidlc`, then `/plugin install aidlc@devx-aidlc`). To try a local copy: `claude --plugin-dir <path to this folder>`.

**Cowork:** upload a zip of this folder under Customize, then Plugins.

**Each person needs:** `python3`, git `user.name` and `user.email` set (and listed in `aidlc/project.md`'s team table), the `gh` command signed in (for PRs), the Slack, ClickUp, Google Drive and Google Docs connectors, and to open Claude Code in the repository once and accept the trust dialog.

## First use in a repository

Run `/aidlc:start` in Claude Code. It sets up `aidlc/`, `CLAUDE.md` and `.claude/settings.json`, and asks for the target branch, Slack channel, ClickUp list and team. Review and commit those files yourself.

## Tests

`cd scripts && python3 -m unittest test_aidlc_hooks -v`

## Known limits

- The guard stops the AI from approving its own work by mistake. A person can still turn hooks off or edit files by hand; git history shows it if they do.
- Code written through shell commands (instead of the Write and Edit tools) is not checked by the "finished plan" rule.
- The work runs only while the Claude Code window that started it is open and the laptop is awake. Run `/aidlc:start` again to continue.
- The page has no sign-in yet: being on the developer's laptop is the proof. Others on the team approve in their own session with `/aidlc:approve`.
- Without sign-in, the page link (with its token) is the only key. It is kept out of driver sessions, but the person's own Claude Code session and the Slack DM can see it. The guard blocks the AI from calling the page or the approval code directly; that stops mistakes, not a deliberate workaround. Sign-in is the real fix.
- Don't edit files in the repository folder while the work runs there; use a separate copy for other work.
- A TDD change after `units.md` is written has no defined path yet for `units.md`, its tickets and open branches.
- A module stays with the person who started it. If their driver stops, that module waits until they run it again.
- In Cowork the repository hooks don't apply. The PRD and TDD are approved by the person filling in the Approval section of the Google Doc themselves.
