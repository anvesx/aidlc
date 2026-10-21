---
name: pr
description: The AIDLC PR stage. Prepares a pull request (title, description, reviewers), shows it to the person who started the driver and asks for their guidance, then opens it with gh once they confirm. Never merges. Used for a feature or bug fix (pr.md), units.md (pr-units.md), each module (pr.md in the module folder) and the whole (pr-final.md). Runs in a driver session.
---

# PR

**Job:** open a pull request the person has seen and agreed to. A person who is not the author reviews it, and a person merges it. The target branch only changes through that merge.

Before starting: read `${CLAUDE_PLUGIN_ROOT}/skills/aidlc/rules.md` if you haven't this session. Load `aidlc:asking-questions`.

## Which PR

| File | Branch (head) | What it ships |
|---|---|---|
| `aidlc/work/<task-name>/pr.md` | `feature/<task-name>` | A feature or bug fix |
| `aidlc/work/<task-name>/pr-units.md` | `feature/<task-name>` | `units.md`, before any module branch |
| `aidlc/work/<task-name>/<module>/pr.md` | `feature/<task-name>-<module>` | A module, after its last phase check is Done |
| `aidlc/work/<task-name>/pr-final.md` | `feature/<task-name>-final` | The final check and learnings of the whole |

The base is always the target branch in `project.md`. The current branch is `git branch --show-current`.

## First round: prepare and ask

1. For the `pr.md` of a feature, bug fix or module, create the file from `${CLAUDE_PLUGIN_ROOT}/templates/pr.md`. For `pr-units.md` and `pr-final.md`, the driver already created it with a `Claimed by:` line: fill it in and keep that line. Fill in the branch and the target.
2. Write the proposed title and description from the work's files: the need, the "done" list and how it was checked (with results), changes from the plan, and links to the AIDLC files. Keep it short and plain. Suggest reviewers from the team in `project.md`, never the author.
3. Ask the person who started the driver (their git email is `git config user.email`): question 1 in the template, plus anything else you need. Follow rules: When a stage needs a person (`Waiting for answers`, end).

## Next round: open it

1. Read the answers.
   - **Confirmed** (with or without changes): apply the changes, then open the PR: `gh pr create --base <target> --head <branch> --title "<title>" --body "<description>"` (add `--draft` or `--reviewer` if asked).
   - **Not yet, or a bigger change asked:** apply it, ask again (`Waiting for answers`), and end.
2. Put the PR link in the file and set `Status: Done`. End. The driver waits for the merge where the next stage needs it.
3. If `gh` fails (not installed, not signed in, the branch not on the remote), write the error into the file, set `Waiting for answers`, and ask the person to fix it.

## Never

- Open a PR before the person confirms.
- Merge a PR, or approve a review.
- Push, or change branches (the driver does that).
