# AIDLC

AIDLC is devx's AI-driven development lifecycle. **The AI does the work. People make the decisions.**

Every piece of work runs one loop: **Clarify, Plan, Build, Check, Record.** A feature or bug fix runs it once, in Claude Code. A project or new module starts with a PRD and TDD written as Google Docs in Cowork; then, in the repository, it is split into units, and each unit runs the loop. A driver script runs each stage in a fresh session; people answer and approve. The state lives in files in each project's repository, under `aidlc/`.

This repository holds the AIDLC plugin, in `plugin/aidlc`. See its [README](plugin/aidlc/README.md) for what's inside.

## Install in Claude Code

You need read access to this repository on GitHub. In Claude Code, run once:

```
/plugin marketplace add anvesx/aidlc
/plugin install aidlc@devx-aidlc
```

To get a newer version later: `/plugin marketplace update devx-aidlc`.

## Install in Cowork

Upload a zip of the plugin under Customize, then Plugins. The zip must have `.claude-plugin/plugin.json` at its top level, not inside an `aidlc/` folder:

```
cd plugin/aidlc && zip -r ../../aidlc-plugin.zip . -x '*__pycache__*'
```

For the whole team, the organization Owner installs it.

## Use it

In a project's repository, run `/aidlc:start` in Claude Code. The first time, it sets up `aidlc/`, `CLAUDE.md` and `.claude/settings.json`. After that, tell it what you want done: it starts the work and gives you a link to the AIDLC page, where you follow the work and answer or approve when Slack tells you something needs you. Keep the Claude Code window open while the work runs.

Each person needs `python3`, git `user.name` and `user.email` set, `gh` signed in, and the Slack, ClickUp, Google Drive and Google Docs connectors.

## Try a local copy

`claude --plugin-dir ./plugin/aidlc`

## Tests

`cd plugin/aidlc/scripts && python3 -m unittest test_aidlc_hooks -v`
