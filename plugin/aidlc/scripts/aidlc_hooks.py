#!/usr/bin/env python3
"""AIDLC hooks: session-start, guard, approve, stop.

Usage (from hooks/hooks.json):  aidlc_hooks.py <session-start|guard|approve|stop>
Reads the hook input (JSON) on stdin. Standard library only; Python 3.8 or later.

What each one does:
  session-start  Loads aidlc/index.md, aidlc/project.md, where open work stands, and the
                 plugin folder and driver command.
  guard          (PreToolUse) Blocks the AI from: writing approval lines; editing code
                 when no work has a finished plan; editing files marked Done (except to
                 mark them Stale); marking a step Done that needs approval and has none;
                 turning "Approval needed: yes" into "no"; setting a file to Approved;
                 changing anything but links in units.md while it is Approved; changing a
                 "Claimed by:" line; editing an active decision (except to mark it Replaced).
  approve        (UserPromptSubmit) When the person types /aidlc:approve: pulls, checks the
                 person may approve this file (team table in aidlc/project.md), records the
                 approval under their git identity, commits it and pushes it.
  stop           (Stop) Makes sure every AIDLC work file has a valid status line. In a
                 person's own session (not a driver session) on a feature/ branch, commits
                 and pushes their changes to aidlc/work/ (their answers).

The guard is a guard against mistakes, not a security boundary: a person can turn hooks
off, and shell commands that write files are only partly checked. Git history shows what
happened either way.
"""

import datetime
import json
import os
import re
import subprocess
import sys

STATUSES = ["Draft", "Waiting for answers", "Waiting for approval", "Waiting for go-back approval",
            "Approved", "Done", "Stale"]
STEP_ORDER = ["clarify.md", "plan.md", "build-log.md", "check-assessment.md", "learnings.md"]
STATUS_LINE = re.compile(r"^Status:[ \t]*(.*?)[ \t]*$", re.M)
APPROVAL_NEEDED = re.compile(r"^Approval needed:[ \t]*(.*?)[ \t]*$", re.M | re.I)
GO_BACK_TO = re.compile(r"^Go back to:[ \t]*`?([\w.\-]+)`?", re.M | re.I)
# A real approval line: "Approved by: <value>" where the value isn't a template placeholder.
APPROVAL_LINE = re.compile(r"^[^\w\n]*(?:go-back\s+)?approved by:[ \t]*(?!<)\S.*$", re.M | re.I)
# The same, inside a shell command or tool argument (not at a line start; skips quotes).
APPROVAL_IN_TEXT = re.compile(r"(?:go-back\s+)?approved by:[ \t]*[^<\s\"'`\\][^\"'`\n]{2,}", re.I)
APPROVE_PROMPT = re.compile(r"^\s*/(?:aidlc:)?approve\b[ \t]*([^\n`]*)", re.I)
APPROVE_EXPANDED = re.compile(r"The person typed `/aidlc:approve\b[ \t]*([^`\n]*)`")
FILE_TOOLS = {"Write", "Edit", "MultiEdit"}
CLAIM_LINE = re.compile(r"^Claimed by:[ \t]*(.*?)[ \t]*$", re.M)
EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
URL = re.compile(r"https?://[^\s|)>\]]+")
MD_LINK = re.compile(r"\[[^\]\n]*\]\(\s*https?://[^)\s]*\s*\)")
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE_ACTION = "/api/act"  # the AIDLC page's address for answers and approvals
STAGE_MARKER = "aidlc-stage-running"  # in .git/ while the driver runs a stage in this folder


# ---------- helpers ----------

def read_input():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def find_root(start):
    """The nearest folder at or above `start` that has an aidlc/ folder."""
    path = os.path.abspath(start or os.getcwd())
    if os.path.isfile(path):
        path = os.path.dirname(path)
    while True:
        if os.path.isdir(os.path.join(path, "aidlc")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def project_dir(data):
    return os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()


def read_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def status_of(text):
    m = STATUS_LINE.search(text or "")
    return m.group(1).strip() if m else None


def approval_needed(text):
    m = APPROVAL_NEEDED.search(text or "")
    return bool(m) and m.group(1).strip().lower().startswith("yes")


def links_out(text):
    """The text without its status line, links, <placeholders> and spacing: what may not change
    while units.md is Approved."""
    text = URL.sub("", MD_LINK.sub("", without_status(text)))
    text = re.sub(r"<[^<>\n]*>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def without_status(text):
    return STATUS_LINE.sub("Status:", text or "", count=1)


def approval_lines(text):
    return {line.strip() for line in APPROVAL_LINE.findall(text or "")}


def work_files(root):
    """Every .md file under aidlc/work/."""
    base = os.path.join(root, "aidlc", "work")
    for dirpath, _, files in os.walk(base):
        for name in sorted(files):
            if name.endswith(".md"):
                yield os.path.join(dirpath, name)


def rel(root, path):
    return os.path.relpath(path, root)


def inside(path, folder):
    path, folder = os.path.abspath(path), os.path.abspath(folder)
    return path == folder or path.startswith(folder + os.sep)


def emit_context(event, text, user_message=None):
    out = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}
    if user_message:
        out["systemMessage"] = user_message
    print(json.dumps(out))


def block(reason):
    print("AIDLC: " + reason, file=sys.stderr)
    sys.exit(2)


def git(root, *args):
    return subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True)


def is_driver_session():
    return os.environ.get("AIDLC_DRIVER") == "1"


def claim_of(text):
    m = CLAIM_LINE.search(text or "")
    return m.group(1).strip() if m else None


def claim_email(folder):
    """The git email on the 'Claimed by:' line of clarify.md in `folder`, or None."""
    claim = claim_of(read_text(os.path.join(folder, "clarify.md")))
    m = EMAIL.search(claim or "")
    return m.group(0).lower() if m else None


def team(root):
    """Rows of the Team table in aidlc/project.md, as dicts with 'name', 'email', 'slack', 'role'."""
    text = read_text(os.path.join(root, "aidlc", "project.md")) or ""
    m = re.search(r"^## Team[ \t]*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return []
    rows, header = [], None
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        row = dict(zip(header, cells))
        email = EMAIL.search(row.get("git email", ""))
        if email:
            rows.append({"name": row.get("name", ""), "email": email.group(0).lower(),
                         "slack": row.get("slack user id", ""), "role": row.get("role", "").lower()})
    return rows


def approver_rule(root, path):
    """Who may approve `path`: (a plain description, a function email -> bool)."""
    folder = os.path.dirname(path)
    name = os.path.basename(path)
    people = team(root)
    in_team = {p["email"] for p in people}

    def with_role(role):
        return {p["email"] for p in people if p["role"] == role}

    if name == "units.md":
        allowed = with_role("tech lead")
        return "the tech lead", lambda e: e in allowed
    if name == "phase-check.md":
        claimers = set()
        for entry in sorted(os.listdir(folder)):
            sub = os.path.join(folder, entry)
            if os.path.isdir(sub):
                email = claim_email(sub)
                if email:
                    claimers.add(email)
        return "a developer who claimed a unit in this phase", lambda e: e in claimers and e in in_team
    if os.path.exists(os.path.join(folder, "units.md")):
        allowed = with_role("qa")
        return "QA", lambda e: e in allowed
    claimer = claim_email(folder)
    return ("the developer who claimed this work ({})".format(claimer or "no 'Claimed by:' line found"),
            lambda e: claimer is not None and e == claimer and e in in_team)


def has_upstream(root):
    return git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").returncode == 0


def push(root):
    """Push the current branch. Returns an error line, or None."""
    args = ["push"] if has_upstream(root) else ["push", "-u", "origin", "HEAD"]
    result = git(root, *args)
    if result.returncode != 0:
        lines = (result.stderr or result.stdout or "unknown git error").strip().splitlines()
        return lines[-1] if lines else "unknown git error"
    return None


# ---------- session start ----------

def session_start(data):
    start = project_dir(data)
    root = find_root(start)
    if not root:
        if git(start, "rev-parse", "--is-inside-work-tree").returncode == 0:
            emit_context("SessionStart", "AIDLC is not set up in this repository yet. "
                         "/aidlc:start sets it up.")
        return 0
    parts = ["AIDLC is set up in this repository. Follow the aidlc skill and its rules for all work."]
    plugin = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin:
        parts.append("AIDLC plugin folder: {0}\nTemplates: {0}/templates\nDriver command: python3 \"{0}/scripts/aidlc_driver.py\" <task-name> [\"<request>\" | --tdd \"<approved TDD copy link>\"]".format(plugin))
    parts.append("This is a driver session: run only the stage the driver names." if is_driver_session()
                 else "This is a person's own session: never run a stage here (see the aidlc skill).")
    for name in ("index.md", "project.md"):
        text = read_text(os.path.join(root, "aidlc", name))
        if text:
            if len(text) > 6000:
                text = text[:6000] + "\n... (cut; read the file for the rest)"
            parts.append("--- aidlc/{} ---\n{}".format(name, text.strip()))
    open_lines = []
    for path in work_files(root):
        status = status_of(read_text(path))
        if status != "Done":
            open_lines.append("- {}: {}".format(rel(root, path), status or "NO STATUS LINE"))
    if open_lines:
        parts.append("--- Open AIDLC work (files not Done) ---\n" + "\n".join(open_lines))
    emit_context("SessionStart", "\n\n".join(parts))
    return 0


# ---------- guard ----------

def apply_edit(text, old, new, replace_all=False):
    if not old or old not in text:
        return text
    return text.replace(old, new) if replace_all else text.replace(old, new, 1)


def new_text_for(tool, tool_input, old_text):
    if tool == "Write":
        return tool_input.get("content", "")
    if tool == "Edit":
        return apply_edit(old_text, tool_input.get("old_string", ""), tool_input.get("new_string", ""),
                          tool_input.get("replace_all", False))
    if tool == "MultiEdit":
        text = old_text
        for e in tool_input.get("edits", []) or []:
            text = apply_edit(text, e.get("old_string", ""), e.get("new_string", ""), e.get("replace_all", False))
        return text
    return old_text


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings_in(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings_in(v)


def has_finished_plan(root):
    """True if some work folder has plan.md Done and its check not yet Done."""
    base = os.path.join(root, "aidlc", "work")
    for dirpath, _, files in os.walk(base):
        if "plan.md" in files and status_of(read_text(os.path.join(dirpath, "plan.md"))) == "Done":
            check = read_text(os.path.join(dirpath, "check-assessment.md"))
            if check is None or status_of(check) != "Done":
                return True
    return False


def guard(data):
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}

    # Approvals through the shell or any other tool (for example a Google Docs update), and any
    # call to the AIDLC page's address: only a person's click there records answers or approvals.
    if tool not in FILE_TOOLS:
        if tool in ("Bash", "WebFetch", "NotebookEdit") or tool.startswith("mcp__"):
            for s in strings_in(tool_input):
                if PAGE_ACTION in s or "record_approval" in s:
                    block("the AIDLC page is for the person only. Calling its address to answer or approve "
                          "is blocked; ask the person to do it on the page.")
                if APPROVAL_IN_TEXT.search(s):
                    block("only the person can approve. Writing an 'Approved by' line is blocked. "
                          "Ask the person to approve (in a Google Doc they fill in the Approval section "
                          "themselves; in the repository they run /aidlc:approve).")
        return 0

    path = tool_input.get("file_path") or ""
    if not path:
        return 0
    path = os.path.abspath(os.path.join(project_dir(data), path))
    old_text = read_text(path) or ""
    new_text = new_text_for(tool, tool_input, old_text)

    # 0. No file (a script, say) that would call the AIDLC page or record an approval, outside the plugin.
    plugin_source = os.sep + os.path.join("plugin", "aidlc") + os.sep in path  # the plugin's own repository
    if not inside(path, PLUGIN_ROOT) and not plugin_source and any(x in new_text and x not in old_text for x in (PAGE_ACTION, "record_approval")):
        block("the AIDLC page and approvals are for the person only. Writing code that calls them is blocked.")

    # 1. The AI never writes an approval line.
    if approval_lines(new_text) - approval_lines(old_text):
        block("only the person can approve. Writing an 'Approved by' line is blocked. "
              "Set the file to 'Status: Waiting for approval' and ask the person to run /aidlc:approve.")

    root = find_root(os.path.dirname(path)) or find_root(project_dir(data))
    if not root or not inside(path, root):
        return 0
    aidlc = os.path.join(root, "aidlc")

    if inside(path, os.path.join(aidlc, "work")):
        old_status, new_status = status_of(old_text), status_of(new_text)
        # 2. A Done file is never edited, except to mark it Stale.
        if old_text and old_status == "Done":
            if new_status != "Stale" or without_status(new_text) != without_status(old_text):
                block("{} is Done and can't be edited. To redo it, change only its status line to "
                      "'Status: Stale' (see the rules: Going back).".format(rel(root, path)))
        # 2b. Only the approve hook sets Approved.
        if new_status == "Approved" and old_status != "Approved":
            block("only the approve hook sets 'Status: Approved' in {}. Set 'Status: Waiting for approval' "
                  "and ask the tech lead to run /aidlc:approve.".format(rel(root, path)))
        # 2c. While units.md is Approved, only links (ticket links) may change.
        if old_status == "Approved":
            if new_status not in ("Approved", "Done") or links_out(new_text) != links_out(old_text):
                block("{} is Approved: only ticket links may be added or changed, then the status set to "
                      "Done.".format(rel(root, path)))
        # 2d. A "Claimed by:" line never changes once written.
        if claim_of(old_text) is not None and claim_of(new_text) != claim_of(old_text):
            block("the 'Claimed by:' line in {} can't be changed. It decides who approves this work."
                  .format(rel(root, path)))
        # 3. "Approval needed: yes" can't be turned off.
        if approval_needed(old_text) and not approval_needed(new_text):
            block("'Approval needed: yes' in {} can't be changed to no. That is the person's decision."
                  .format(rel(root, path)))
        # 4. A step that needs approval is only marked Done by the approve hook (an old approval
        #    line from before a go-back doesn't count). The one exception: units.md from Approved.
        if new_status == "Done" and old_status not in ("Done", "Approved") and approval_needed(new_text):
            block("{} needs the person's approval. Set 'Status: Waiting for approval' and ask them to "
                  "run /aidlc:approve.".format(rel(root, path)))
        return 0

    if inside(path, os.path.join(aidlc, "decisions")):
        # 5. An active decision is never edited, except to mark it replaced.
        if old_text and (status_of(old_text) or "").lower() == "active":
            new_status = status_of(new_text) or ""
            if not new_status.lower().startswith("replaced by") \
                    or without_status(new_text) != without_status(old_text):
                block("{} is an active decision and can't be edited. Write a new decision that "
                      "replaces it, then change only this one's status to 'Replaced by D-NNN'."
                      .format(rel(root, path)))
        return 0

    # 5b. A driver session never changes the project's Claude settings (the git deny lives there).
    #     In a person's own session (setup, or a change they ask for) they may change.
    if inside(path, os.path.join(root, ".claude")):
        if is_driver_session():
            block("a driver session can't change {}. Ask a person (Waiting for answers).".format(rel(root, path)))
        return 0

    if inside(path, aidlc) or inside(path, os.path.join(root, ".git")) \
            or os.path.basename(path) == "CLAUDE.md":
        return 0

    # 6. No code changes without a finished plan.
    if not has_finished_plan(root):
        block("no AIDLC work has a finished plan (plan.md marked Done), so changing {} is blocked. "
              "Run /aidlc:start and finish Clarify and Plan first.".format(rel(root, path)))
    return 0


# ---------- approve ----------

def record_approval(root, path, status):
    """Record the person's approval (or go-back approval) of `path`, commit and push it.
    Used by /aidlc:approve and by the driver's page. Returns (approved, message)."""
    name = git(root, "config", "user.name").stdout.strip()
    email = git(root, "config", "user.email").stdout.strip()
    if not name or not email:
        return False, ("your git user.name and user.email aren't set, so the approval can't be recorded "
                       "under your name. Set them, then try again. Nothing was approved.")
    who_may, may_approve = approver_rule(root, path)
    if not may_approve(email.strip().lower()):
        return False, ("{} can only be approved by {}, checked against the team table in aidlc/project.md. "
                   "Your git email ({}) doesn't match, so nothing was approved."
                   .format(rel(root, path), who_may, email))
    text = read_text(path) or ""
    today = datetime.date.today().isoformat()
    who = "{} <{}> on {}".format(name, email, today)
    changed = [path]

    if status == "Waiting for approval":
        new_status = "Approved" if os.path.basename(path) == "units.md" else "Done"
        text = STATUS_LINE.sub("Status: " + new_status, text, count=1).rstrip("\n") + \
            "\n\nApproved by: " + who + "\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        done = "{} is approved and marked {}. The driver continues from here.".format(rel(root, path), new_status)
    else:
        target_m = GO_BACK_TO.search(text)
        target = target_m.group(1) if target_m else ""
        if target not in STEP_ORDER:
            return False, ("{} asks to go back but has no valid 'Go back to:' line (one of {}). Nothing was "
                       "approved.".format(rel(root, path), ", ".join(STEP_ORDER[:2])))
        folder = os.path.dirname(path)
        for step in STEP_ORDER[STEP_ORDER.index(target):]:
            step_path = os.path.join(folder, step)
            if step_path == path or not os.path.exists(step_path):
                continue
            step_text = read_text(step_path) or ""
            if status_of(step_text) is not None:
                with open(step_path, "w", encoding="utf-8") as f:
                    f.write(STATUS_LINE.sub("Status: Stale", step_text, count=1))
                changed.append(step_path)
        text = STATUS_LINE.sub("Status: Stale", text, count=1).rstrip("\n") + \
            "\n\nGo-back approved by: " + who + "\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        done = ("going back to {} is approved. These are now Stale and must be redone: {}. "
                "The driver redoes {}.".format(target, ", ".join(rel(root, p) for p in changed), target))

    files = [rel(root, p) for p in changed]
    git(root, "add", "--", *files)
    result = git(root, "commit", "-m", "AIDLC approve: " + rel(root, path), "--", *files)
    if result.returncode != 0:
        lines = (result.stderr or result.stdout or "unknown git error").strip().splitlines()
        done += " (The files were updated but not committed: {})".format(lines[-1] if lines else "unknown")
    else:
        error = push(root)
        if error:
            done += " (Committed but not pushed: {}. Push it, or the driver won't see it.)".format(error)
    return True, "{} approved. {}".format(name, done)


def approve(data):
    prompt = data.get("prompt", "") or ""
    m = APPROVE_PROMPT.match(prompt) or APPROVE_EXPANDED.search(prompt)
    if not m:
        return 0
    wanted = m.group(1).strip()

    def say(text):
        emit_context("UserPromptSubmit", "AIDLC approve: " + text, "AIDLC approve: " + text)
        return 0

    root = find_root(project_dir(data))
    if not root:
        return say("there is no aidlc/ folder in this repository, so nothing was approved.")

    if has_upstream(root):
        pulled = git(root, "pull", "--ff-only")
        if pulled.returncode != 0:
            lines = (pulled.stderr or pulled.stdout or "unknown git error").strip().splitlines()
            return say("couldn't pull the latest from this branch first ({}), so nothing was approved. "
                       "Run /aidlc:start, then /aidlc:approve again.".format(lines[-1] if lines else "unknown"))

    waiting = []
    for path in work_files(root):
        status = status_of(read_text(path))
        if status in ("Waiting for approval", "Waiting for go-back approval"):
            if not wanted or wanted in rel(root, path):
                waiting.append((path, status))
    if not waiting:
        return say("nothing is waiting for approval{}. Nothing was approved."
                   .format(" that matches '{}'".format(wanted) if wanted else ""))
    if len(waiting) > 1:
        names = "\n".join("- " + rel(root, p) for p, _ in waiting)
        return say("more than one thing is waiting, so nothing was approved. Run /aidlc:approve "
                   "with part of the path, for example /aidlc:approve U2/plan.\n" + names)

    path, status = waiting[0]
    approved, message = record_approval(root, path, status)
    return say(message)


# ---------- stop ----------

def stop(data):
    root = find_root(project_dir(data))
    if not root:
        return 0
    problems = []
    for path in work_files(root):
        status = status_of(read_text(path))
        if status not in STATUSES:
            problems.append("- {}: {}".format(rel(root, path),
                                              "no 'Status:' line" if status is None else "unknown status '" + status + "'"))
    if problems:
        if not data.get("stop_hook_active"):
            print(json.dumps({"decision": "block", "reason":
                              "AIDLC: before stopping, give every work file a valid status line "
                              "(one of: {}).\n{}".format(", ".join(STATUSES), "\n".join(problems))}))
        return 0
    if not is_driver_session():
        message = commit_answers(root)
        if message:
            print(json.dumps({"systemMessage": message}))
    return 0


def commit_answers(root):
    """In a person's own session: commit and push their changes to aidlc/work/ (on a feature/ branch)."""
    branch = git(root, "branch", "--show-current").stdout.strip()
    if not branch.startswith("feature/"):
        return None
    git_dir = git(root, "rev-parse", "--absolute-git-dir").stdout.strip()
    if git_dir and os.path.exists(os.path.join(git_dir, STAGE_MARKER)):
        return ("AIDLC: the driver is running a stage in this folder right now, so nothing was committed. "
                "Answer once it is waiting on you again.")
    changed = git(root, "status", "--porcelain", "--", "aidlc/work").stdout.strip()
    if not changed:
        return None
    name = git(root, "config", "user.name").stdout.strip()
    email = git(root, "config", "user.email").stdout.strip()
    if not name or not email:
        return ("AIDLC: your changes in aidlc/work/ were not committed: set git user.name and user.email, "
                "then send any message.")
    git(root, "add", "--", "aidlc/work")
    result = git(root, "commit", "-m", "AIDLC answers", "--", "aidlc/work")
    if result.returncode != 0:
        lines = (result.stderr or result.stdout or "unknown git error").strip().splitlines()
        return "AIDLC: your changes in aidlc/work/ were not committed: {}".format(lines[-1] if lines else "unknown")
    error = push(root)
    if error:
        return "AIDLC: your answers were committed but not pushed ({}). Push them, or the driver won't see them.".format(error)
    return "AIDLC: your answers were committed and pushed on {}. The driver will continue.".format(branch)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("session-start", "guard", "approve", "stop"):
        print("usage: aidlc_hooks.py <session-start|guard|approve|stop>", file=sys.stderr)
        return 1
    data = read_input()
    return {"session-start": session_start, "guard": guard, "approve": approve, "stop": stop}[sys.argv[1]](data)


if __name__ == "__main__":
    sys.exit(main())
