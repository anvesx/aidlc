---
name: units
description: The AIDLC split of a project or new module. After the TDD is approved, writes units.md in the repository (each TDD module split into sequential phases, each phase into units), has the checker check it, gets the tech lead's approval, then creates and links the ClickUp tickets (phase = ticket, unit = subticket). Runs in a driver session. Use when AIDLC work is at units.md.
---

# Units

**Job:** split an approved project or new module into units that can each be built and checked in one session. `units.md` is the source of truth; ClickUp is only a view of it.

Before starting: read `${CLAUDE_PLUGIN_ROOT}/skills/aidlc/rules.md` (especially "Splitting a project or new module") if you haven't this session. Load `aidlc:asking-questions` and `aidlc:test-design`.

## Expertise: a good split

- **Split by working behavior, not by technical layer.** A unit delivers something visible ("A shopper can ..."), not "the database part".
- **Every unit passes the small-enough test** (rules). If one doesn't, split it again.
- **Every PRD ID is in exactly one unit.** Every unit traces to at least one PRD ID or TDD decision. Nothing invented.
- **Everything inside a module runs in order:** phases one after another, and the units of a phase one after another, in table order. Foundation units (setup, shared parts) come first. A unit depends only on earlier units of its module.
- **Parallel work is across modules.** If a module is too big to run one unit at a time, say so to the tech lead (the TDD's modules may need splitting); never plan parallel units inside a module.
- **Dependencies stay inside a module.** A unit depends only on units in the same module. Work across modules goes through module dependencies.
- **Deep steps per unit:** answer the four questions for each unit (rules) and write which steps are deep.

**The checker agent can't reach Google Drive.** When it must check against the PRD or TDD, read the approved copies yourself and give it the text it needs in its prompt.

## Draft: write units.md

The driver created `units.md` with the approved TDD copy's link.

1. Read the approved TDD copy (never the working doc) and the approved PRD copy linked from it, with the Google Drive connector. Note the TDD copy's last-modified time in "TDD copy last modified when split", and fill in the PRD link.
2. If the work touches existing code, use the `aidlc:code-reader` agent for what you need to know to split it. Mark statements Checked or Assumed.
3. Keep the headings and table columns exactly as in the template (`## Modules ...`, `## <module>`, `### Phase <N>: <name>`, and the unit table's columns): the driver reads them to make branches and claim units. Folders are `<module>/phase-<N>-<name>/U<n>-<name>/`, unit IDs restart at U1 in each module, and "Depends on" lists earlier unit IDs of the same module (or `none`).
4. Write `units.md`: the modules from the TDD (with branch `feature/<task-name>-<module>` and module dependencies; module names unique and never `final`); for each module, phases; for each phase, units with folder, behavior, short yes/no "done" list, PRD IDs and TDD decisions, depends on, deep steps. Leave the ticket fields empty.
5. Fill the coverage table and the two checks. Copy the TDD's shared decisions.
6. Questions for the tech lead: write them into the "Questions and answers" table with options and your suggested answer, and follow rules: When a stage needs a person (`Waiting for answers`, tag the tech lead, end). In a later round, apply the answers.
7. Start the `aidlc:checker` agent: `units.md` against the approved TDD and PRD (every PRD ID in exactly one unit, every unit traces to a PRD ID or TDD decision, every unit small enough, dependencies only inside a module, phases in a workable order, nothing invented). Fix, up to 2 rounds.
8. Set `Status: Waiting for approval`, put a short summary for the tech lead under the title (modules, phases, units, anything they should look at), and end. When the tech lead runs `/aidlc:approve`, the hook sets `Approved`.

## Approved: create the tickets

While `units.md` is `Approved`, only ticket links may be added or changed (a hook enforces it).

1. For each phase, create a ClickUp task in the list named in `project.md`: title `<task-name> <module> phase <N>: <name>`, description with what the phase delivers and the path to `units.md`. Put its link on the phase's "Phase ticket:" line.
2. For each unit, create a subtask of its phase's task: title `U<n> <name>`, description with its behavior and "done" list. Put its link in the unit's "Ticket" column.
3. If a ticket can't be created, say why in the session output, leave the status `Approved`, and end; the driver tries again and stops after 2 runs.
4. When every phase and unit has a link: set `Status: Done` and end. The driver then runs the PR for `units.md` (`pr-units.md`), which must be merged before any module branch is made.

## Never

- Put a PRD ID in two units, or leave one out.
- Change anything but ticket links while `units.md` is `Approved`.
- Create tickets before the tech lead's approval.
- Fill in or change an approval.
