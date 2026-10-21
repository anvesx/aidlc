#!/usr/bin/env python3
"""AIDLC driver: runs one piece of work, one fresh headless Claude session per stage.

Normally /aidlc:start starts it for you, in the background of your Claude Code window, and
gives you the link to the AIDLC page. It stops when that Claude Code window closes.
It can also be run from a terminal, inside the project's repository:

  python3 aidlc_driver.py <task-name> "<request or ClickUp link>"    new feature or bug fix
  python3 aidlc_driver.py <task-name> --tdd "<approved TDD copy link>"  new project or module
  python3 aidlc_driver.py <task-name>                                 continue, or take another module

What it does, in a loop:
  1. Fetches, reads the AIDLC files on the work's branches, and finds the next stage.
  2. Runs that stage in a fresh headless session: claude -p "/aidlc:start <stage file>",
     with AIDLC_DRIVER=1 so the session knows it is a driver session, and shows what the
     session does, step by step, on the page.
  3. Commits and pushes what the session changed (after checking that no file that needs
     approval was set to Done or Approved by a session).
  4. If the next stage waits on the developer, they answer or approve on the page, and it
     carries on at once. Otherwise it checks again every few minutes.
It also makes branches and claims units. Inside a module, units run one after another on the
module's branch; parallel work is a second person running the driver, which takes another module.
It stops when the work is complete, on any git problem, when the same stage runs twice without
its status changing (it posts in Slack first), or when the watched Claude Code window closes
(a step that is running is cut off and its half-done changes are thrown away).

It asks once for approval to commit and push to this work's own branches (feature/...), or
takes --approved when /aidlc:start has asked in the chat. It never pushes to the target branch;
that only changes through a PR a person merges. Standard library only; Python 3.8 or later.
"""

import argparse
import collections
import datetime
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aidlc_hooks as H  # noqa: E402  (shared status and team helpers)
import aidlc_page  # noqa: E402  (the local page)

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(PLUGIN, "templates")
SMALL_STEPS = ["clarify.md", "plan.md", "build-log.md", "check-assessment.md", "learnings.md", "pr.md"]
UNIT_STEPS = SMALL_STEPS[:5]
RESERVED_MODULES = ("final",)
# Claude Code's personal settings file: never checked, never committed.
NOT_OURS = ["--", ".", ":(exclude).claude/settings.local.json"]
FINAL_STEPS = ["check-assessment.md", "learnings.md", "pr-final.md"]
WAITING = ("Waiting for answers", "Waiting for approval", "Waiting for go-back approval")
TASK_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STATE_FILE = "aidlc-driver.json"  # in .git/: which driver runs here, and its page link


class Stopped(Exception):
    """The watched Claude Code window closed: stop at once."""


def describe_tool(name, inp):
    """One plain line for what a session is doing."""
    inp = inp or {}
    path = os.path.basename(str(inp.get("file_path") or inp.get("path") or inp.get("notebook_path") or ""))
    if name == "Read":
        return "Reading " + path
    if name == "Write":
        return "Writing " + path
    if name in ("Edit", "MultiEdit"):
        return "Editing " + path
    if name == "Bash":
        return "Running: " + one_line(str(inp.get("description") or inp.get("command") or ""))[:110]
    if name == "Grep":
        return "Searching for \"{}\"".format(str(inp.get("pattern", ""))[:60])
    if name == "Glob":
        return "Finding files " + str(inp.get("pattern", ""))[:60]
    if name in ("Agent", "Task"):
        return "Started the {} agent: {}".format(inp.get("subagent_type", "sub"), one_line(str(inp.get("description", "")))[:90])
    if name == "Skill":
        return "Using the {} skill".format(inp.get("skill", ""))
    if name == "TodoWrite":
        return "Updating its to-do list"
    if "Slack" in name:
        return "Posting in Slack"
    if "ClickUp" in name:
        return "ClickUp: " + name.split("clickup_")[-1].replace("_", " ")
    if "Google_Drive" in name or "Google_Docs" in name:
        return "Reading from Google Drive"
    return name.replace("mcp__", "").replace("__", ": ")


class Stop(Exception):
    """Stop the driver with a message. notify=True also posts it in Slack."""
    def __init__(self, message, notify=True):
        super().__init__(message)
        self.notify = notify


def one_line(text):
    return re.sub(r"\s+", " ", (text or "").replace("|", "/")).strip()


# ---------- units.md ----------

def table_rows(lines):
    """Yield (header, rows) for each markdown table in `lines`. Header cells are lowercase."""
    header, rows = None, []
    for line in lines + [""]:
        line = line.strip()
        if line.startswith("|"):
            cells = [c.strip().strip("`").strip() for c in line.strip("|").split("|")]
            if header is None:
                header = [c.lower() for c in cells]
            elif not all(set(c) <= set("-: ") for c in cells):
                rows.append(dict(zip(header, cells)))
        elif header is not None:
            yield header, rows
            header, rows = None, []


def column(row, *starts):
    for key, value in row.items():
        if any(key.startswith(s) for s in starts):
            return value
    return ""


def names(cell):
    cell = (cell or "").strip()
    if not cell or cell.lower() in ("none", "-", "no"):
        return []
    return [n.strip() for n in re.split(r"[,;]", cell) if n.strip()]


def parse_units(text):
    """Modules in order: [{name, depends, phases: [{title, units: [{id, folder, depends, behavior}]}]}]."""
    lines = (text or "").replace("\r", "").splitlines()
    modules, by_name = [], {}
    section = None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            section = line[3:].strip()
            if section.lower().startswith("modules"):
                block = []
                for nxt in lines[i + 1:]:
                    if nxt.startswith("## "):
                        break
                    block.append(nxt)
                for header, rows in table_rows(block):
                    if "module" in header:
                        for row in rows:
                            name = row.get("module", "").strip()
                            if name and not name.startswith("<"):
                                m = {"name": name, "depends": names(column(row, "depends on")), "phases": []}
                                modules.append(m)
                                by_name[name] = m
    # Phases and units, per module section.
    current_module, current_phase, block = None, None, []

    def flush():
        if current_module is None or current_phase is None:
            return
        for header, rows in table_rows(block):
            if "unit" in header and "folder" in header:
                for row in rows:
                    uid = row.get("unit", "").strip()
                    folder = row.get("folder", "").strip().strip("/")
                    if not uid or uid.startswith("<") or not folder or "<" in folder:
                        continue
                    current_phase["units"].append({
                        "id": uid, "folder": folder,
                        "depends": names(column(row, "depends on")),
                        "behavior": column(row, "behavior")})

    for line in lines:
        if line.startswith("## "):
            flush()
            block, current_phase = [], None
            current_module = by_name.get(line[3:].strip())
        elif line.startswith("### ") and current_module is not None:
            flush()
            block = []
            current_phase = {"title": line[4:].strip(), "units": []}
            current_module["phases"].append(current_phase)
        else:
            block.append(line)
    flush()

    problems = []
    if not modules:
        problems.append("no modules in the Modules table")
    seen = set()
    for m in modules:
        if m["name"] in seen:
            problems.append("module {} is listed twice in the Modules table".format(m["name"]))
        seen.add(m["name"])
    # Module dependencies must not loop (a module can't wait for itself, directly or not).
    state = {}

    def visit(name, path):
        if state.get(name) == "done":
            return
        if state.get(name) == "visiting":
            problems.append("module dependencies loop: " + " -> ".join(path + [name]))
            return
        state[name] = "visiting"
        for dep in by_name.get(name, {}).get("depends", []):
            if dep in by_name:
                visit(dep, path + [name])
        state[name] = "done"

    for m in modules:
        visit(m["name"], [])
    for m in modules:
        for dep in m["depends"]:
            if dep not in by_name:
                problems.append("module {} depends on unknown module {}".format(m["name"], dep))
        if m["name"].lower() in RESERVED_MODULES or not TASK_NAME.match(m["name"]):
            problems.append("module name '{}' must be lowercase words joined by - and not 'final'".format(m["name"]))
        ids, phase_dirs = set(), set()
        for phase in m["phases"]:
            dirs = {os.path.dirname(u["folder"]) for u in phase["units"]}
            if len(dirs) > 1:
                problems.append("{} {}: its units are in different phase folders ({})".format(
                    m["name"], phase["title"], ", ".join(sorted(dirs))))
            for d in dirs:
                if d in phase_dirs:
                    problems.append("{}: two phases use the folder {}".format(m["name"], d))
                phase_dirs.add(d)
            if not phase["units"]:
                problems.append("{} {} has no units".format(m["name"], phase["title"]))
            for u in phase["units"]:
                if u["id"] in ids:
                    problems.append("{} has two units named {}".format(m["name"], u["id"]))
                for dep in u["depends"]:
                    if dep not in ids:
                        problems.append("{} {} depends on {}, which is not an earlier unit of {} (units run "
                                        "in table order)".format(m["name"], u["id"], dep, m["name"]))
                ids.add(u["id"])
                if not re.match(r"^{}/phase-\d+-[a-z0-9-]+/U\d+-[a-z0-9-]+$".format(re.escape(m["name"])), u["folder"]):
                    problems.append("{} {}: folder {} is not <module>/phase-<N>-<name>/U<n>-<name>/".format(
                        m["name"], u["id"], u["folder"]))
        if not m["phases"]:
            problems.append("module {} has no phases".format(m["name"]))
    if problems:
        raise Stop("units.md couldn't be read by the driver: " + "; ".join(problems))
    return modules


# ---------- the driver ----------

class Driver:
    def __init__(self, args):
        self.args = args
        self.task = args.task
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if top.returncode != 0:
            raise Stop("run this inside the project's git repository.", notify=False)
        self.root = top.stdout.strip()
        self.folder = "aidlc/work/" + self.task
        project = H.read_text(os.path.join(self.root, "aidlc", "project.md"))
        if not project:
            raise Stop("aidlc/project.md not found. Run /aidlc:start in Claude Code first to set up AIDLC.",
                       notify=False)
        self.target = self.setting(project, "Target branch")
        self.channel = self.setting(project, "Slack channel ID")
        if not self.target:
            raise Stop("aidlc/project.md has no 'Target branch:' line.", notify=False)
        self.name = self.git_out("config", "user.name")
        self.email = self.git_out("config", "user.email").lower()
        if not self.name or not self.email:
            raise Stop("set git user.name and user.email first.", notify=False)
        self.slack = next((p["slack"] for p in H.team(self.root) if p["email"] == self.email), "")
        self.same_runs = {}
        self.last_wait = None
        # What the page shows, and what it shares with the driver loop.
        self.is_project = False
        self.feature_steps, self.unit_steps, self.final_steps = SMALL_STEPS, UNIT_STEPS, FINAL_STEPS
        self.parse_units = parse_units
        self.phase, self.message = "starting", ""
        self.current, self.waiting = None, None
        self.started = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        self.activity = collections.deque(maxlen=400)
        self.lock = threading.Lock()   # one git user at a time: the loop or the page
        self.wake = threading.Event()  # set by the page after an answer or approval
        self.stopping = threading.Event()
        self.proc = None
        self.page = None
        self.seq = 0             # activity event number, so the page can follow new events
        self.cut_off = False     # a running step was cut off by the window closing
        self.notified = set()    # (branch, path, status) already sent to Slack

    # --- small helpers ---

    @staticmethod
    def setting(text, label):
        m = re.search(r"^-?\s*" + re.escape(label) + r":[ \t]*(.+?)[ \t]*$", text, re.M | re.I)
        value = m.group(1).strip() if m else ""
        return "" if value.startswith("<") else value

    def git(self, *args, check=True):
        result = subprocess.run(["git", "-C", self.root] + list(args), capture_output=True, text=True)
        if check and result.returncode != 0:
            lines = (result.stderr or result.stdout or "").strip().splitlines()
            raise Stop("git {} failed: {}".format(" ".join(args), lines[-1] if lines else "unknown error"))
        return result

    def git_out(self, *args):
        return self.git(*args, check=False).stdout.strip()

    def remote_has(self, branch):
        return self.git("rev-parse", "--verify", "--quiet", "refs/remotes/origin/" + branch, check=False).returncode == 0

    def read_at(self, branch, path):
        result = self.git("show", "origin/{}:{}".format(branch, path), check=False)
        return result.stdout.replace("\r", "") if result.returncode == 0 else None

    def status_at(self, branch, path):
        return H.status_of(self.read_at(branch, path))

    def claim_at(self, branch, folder):
        m = H.EMAIL.search(H.claim_of(self.read_at(branch, folder + "/clarify.md")) or "")
        return m.group(0).lower() if m else None

    def local_status(self, path):
        return H.status_of(H.read_text(os.path.join(self.root, path)))

    def say(self, text):
        print("[aidlc {}] {}".format(datetime.datetime.now().strftime("%H:%M"), text), flush=True)
        self.log("driver", text)

    def log(self, kind, text, stage=None):
        self.seq += 1
        self.activity.append({"n": self.seq, "t": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "kind": kind,
                              "text": text, "stage": stage or (self.current or {}).get("path")})

    def request_text(self):
        for branch in ("feature/" + self.task, self.target):
            text = self.read_at(branch, self.folder + "/clarify.md")
            if text:
                m = re.search(r"^\| Source \|(.*)\|\s*$", text, re.M)
                if m:
                    return m.group(1).strip()
        return self.args.request or self.args.tdd or ""

    # --- branches and commits ---

    def switch_to(self, branch, create_from=None):
        if self.git_out("status", "--porcelain", *NOT_OURS):
            raise Stop("the working tree has uncommitted changes, so the driver can't switch branches.")
        local = self.git("rev-parse", "--verify", "--quiet", "refs/heads/" + branch, check=False).returncode == 0
        if local:
            self.git("switch", "-q", branch)
            if self.remote_has(branch):
                self.git("branch", "-q", "--set-upstream-to", "origin/" + branch)
                self.git("pull", "-q", "--ff-only")
        elif self.remote_has(branch):
            self.git("switch", "-q", "-c", branch, "--track", "origin/" + branch)
        else:
            base = create_from or self.target
            self.git("switch", "-q", "-c", branch, "origin/" + base)
            if self.git("push", "-q", "-u", "origin", branch, check=False).returncode != 0:
                # Another driver made this branch at the same moment: use theirs (ours has no commits).
                self.git("fetch", "-q", "origin")
                if not self.remote_has(branch):
                    raise Stop("couldn't push the new branch {}.".format(branch))
                self.git("reset", "-q", "--hard", "origin/" + branch)
                self.git("branch", "-q", "--set-upstream-to", "origin/" + branch)
                return
            self.say("made branch {} from {}".format(branch, base))

    def check_approvals(self):
        """Item 27: a file that needs approval only becomes Done or Approved through the approve
        hook's own commit, never in a commit the driver makes for a session. The one exception is
        units.md going from Approved to Done (after its tickets), which needs an approval commit."""
        staged = self.git_out("diff", "--cached", "--name-only", "--", self.folder).splitlines()
        for rel in staged:
            if not rel.endswith(".md"):
                continue
            text = H.read_text(os.path.join(self.root, rel))
            status = H.status_of(text)
            if status not in ("Done", "Approved") or not H.approval_needed(text):
                continue
            before = H.status_of(self.git("show", "HEAD:" + rel, check=False).stdout)
            if before == status:
                continue
            subjects = self.git_out("log", "--full-history", "--format=%s", "--", rel).splitlines()
            if not (before == "Approved" and status == "Done" and "AIDLC approve: " + rel in subjects):
                raise Stop("{} needs approval but was set to {} by a session, not by /aidlc:approve. "
                           "Nothing was committed; a person must look at it.".format(rel, status))

    def commit_and_push(self, message):
        self.git("add", "-A", *NOT_OURS)
        if self.git("diff", "--cached", "--quiet", check=False).returncode == 0:
            return False
        self.check_approvals()
        self.git("commit", "-q", "-m", message)
        if self.git("push", "-q", check=False).returncode == 0:
            return True
        # Someone else pushed to this branch meanwhile (another driver running the same shared
        # stage, or a person's answers). Put this commit on top if it doesn't clash; otherwise
        # drop it, because the other push already did this stage.
        branch = self.git_out("branch", "--show-current")
        if self.git("pull", "-q", "--rebase", check=False).returncode == 0:
            self.check_approvals()
            if self.git("push", "-q", check=False).returncode == 0:
                return True
        self.git("rebase", "--abort", check=False)
        self.git("fetch", "-q", "origin")
        self.git("reset", "-q", "--hard", "origin/" + branch)
        self.say("another push to {} came first and clashed with this run; dropped this run's changes "
                 "and picking again".format(branch))
        return False

    def from_template(self, name, path, replacements, claim=False):
        text = H.read_text(os.path.join(TEMPLATES, name))
        if text is None:
            raise Stop("template {} not found in the plugin.".format(name))
        for pattern, value in replacements:
            text = re.sub(pattern, lambda _m, v=value: v, text, count=1, flags=re.M)
        if claim and not H.claim_of(text):
            text = re.sub(r"^(Approval needed:.*)$", lambda m: m.group(1) + "\n" + self.claim_text(),
                          text, count=1, flags=re.M)
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)

    def claim_text(self):
        return "Claimed by: {} <{}> on {}".format(self.name, self.email, datetime.date.today().isoformat())

    def write_clarify(self, folder, source):
        self.from_template("clarify.md", folder + "/clarify.md", [
            (r"^Claimed by:.*$", self.claim_text()),
            (r"^\| Task \|.*$", "| Task | {} |".format(self.task)),
            (r"^\| Source \|.*$", "| Source | {} |".format(one_line(source))),
        ])

    # --- sessions ---

    def people_for(self, branch, path):
        """Who a waiting file waits on (rules: Who to tag), as rows of the team table."""
        team = H.team(self.root)
        folder, name = os.path.dirname(path), os.path.basename(path)

        def by_email(emails):
            emails = {e.lower() for e in emails if e}
            return [p for p in team if p["email"] in emails] or \
                [{"name": e, "email": e, "slack": self.slack if e == self.email else "", "role": ""} for e in emails]

        def by_role(role):
            return [p for p in team if p["role"] == role]
        if name == "units.md":
            return by_role("tech lead")
        if name in ("pr.md", "pr-units.md", "pr-final.md"):
            return by_email([self.email])
        if name == "phase-check.md":
            listing = self.git_out("ls-tree", "--name-only", "origin/" + branch, folder + "/").splitlines()
            return by_email([self.claim_at(branch, entry) for entry in listing] or [self.email])
        if self.is_project and folder == self.folder:
            return by_role("qa") if name == "check-assessment.md" else by_role("tech lead")
        return by_email([self.claim_at(branch, folder) or self.email])

    def notify(self, text, people=None):
        """A Slack DM to each person (default: the person running the driver)."""
        people = people if people is not None else [{"email": self.email, "slack": self.slack}]
        for person in people:
            slack = person.get("slack", "")
            if not slack:
                self.say("no Slack user ID for {} in aidlc/project.md, so no DM was sent.".format(person.get("email")))
                continue
            prompt = ("Send this exact message as a direct message to the Slack user with ID {0}, using the Slack "
                      "tool with {0} as the channel. Do nothing else.\n\n<@{0}> AIDLC {1}: {2}".format(slack, self.task, text))
            env = dict(os.environ, AIDLC_DRIVER="1")
            result = subprocess.run([self.args.claude, "-p", prompt], cwd=self.root, env=env,
                                    capture_output=True, text=True)
            if result.returncode != 0:
                self.say("couldn't send the Slack DM: " + (result.stderr or result.stdout).strip()[-200:])

    def tell_waiting(self, branch, path):
        """Once per waiting item: DM whoever it waits on."""
        status = self.status_at(branch, path)
        key = (branch, path, status)
        if key in self.notified or status not in WAITING:
            return
        self.notified.add(key)
        what = {"Waiting for answers": "needs your answers", "Waiting for approval": "needs your approval",
                "Waiting for go-back approval": "proposes going back to an earlier step and needs your decision"}[status]
        label = aidlc_page.STEP_LABELS.get(os.path.basename(path), os.path.basename(path))
        for person in self.people_for(branch, path):
            if person.get("email") == self.email and self.page:
                where = "Open the AIDLC page: " + self.page.url
            else:
                where = "Open Claude Code in the repository and run /aidlc:start (branch {}).".format(branch)
            self.notify("{} ({}) {}. {}".format(label, path, what, where), [person])

    def run_stage(self, branch, path):
        self.switch_to(branch)
        before = self.local_status(path)
        if before == "Done" or before in WAITING:
            return  # another push moved it on since the fetch; look again
        if not self.claimed_by_me(path):
            return  # another driver claimed this stage
        self.say("running {} on {} (status: {})".format(path, branch, before or "not started"))
        self.current = {"branch": branch, "path": path, "since": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
        self.phase, self.waiting = "running", None
        env = dict(os.environ, AIDLC_DRIVER="1")  # the page link (with its token) is never given to sessions
        git_dir = self.git_out("rev-parse", "--absolute-git-dir")
        marker = os.path.join(git_dir, H.STAGE_MARKER)
        logs = os.path.join(git_dir, "aidlc-logs")
        os.makedirs(logs, exist_ok=True)
        log_path = os.path.join(logs, "{}-{}.jsonl".format(datetime.datetime.now().strftime("%Y%m%d-%H%M%S"),
                                                           path.replace("/", "_")))
        with open(marker, "w", encoding="utf-8") as f:
            f.write("{} on {}\n".format(path, branch))
        try:
            code = self.stream_session(["-p", "/aidlc:start " + path, "--output-format", "stream-json", "--verbose"],
                                       env, log_path, path, marker)
            if self.stopping.is_set():
                self.cut_off = True
                raise Stopped()
            after = self.local_status(path)
            if code != 0:
                self.say("the session ended with an error (exit {}).".format(code))
            committed = self.commit_and_push("AIDLC {}: {} ({})".format(self.task, path, after or "no file"))
        finally:
            # Removed only after the commit, so a person's session here never commits a step's changes.
            if os.path.exists(marker) and not self.cut_off:
                os.remove(marker)
            self.current = None
        self.say("{} is now {}{}".format(path, after or "not started", "" if committed else " (nothing to commit)"))
        key = (branch, path)
        if after == before:
            self.same_runs[key] = self.same_runs.get(key, 0) + 1
        else:
            self.same_runs[key] = 0
        if self.same_runs[key] >= 2:
            raise Stop("{} on {} ran twice without its status changing (still '{}'). The driver stopped; "
                       "a person needs to look.".format(path, branch, after or "not started"))

    def stream_session(self, claude_args, env, log_path, stage, marker=None):
        """Run one headless session, logging every line it streams and describing each action."""
        self.proc = subprocess.Popen([self.args.claude] + claude_args, cwd=self.root, env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     start_new_session=True)
        if marker:  # remember the session, so a later start can stop it if this driver was killed
            with open(marker, "a", encoding="utf-8") as f:
                f.write("session pid {}\n".format(self.proc.pid))
        with open(log_path, "w", encoding="utf-8") as log:
            for line in self.proc.stdout:
                log.write(line)
                try:
                    event = json.loads(line)
                except ValueError:
                    event = None
                if not isinstance(event, dict):
                    if line.strip():
                        self.log("output", line.strip()[:200], stage)
                    continue
                sub = bool(event.get("parent_tool_use_id"))
                if event.get("type") == "assistant":
                    for item in (event.get("message") or {}).get("content") or []:
                        if item.get("type") == "tool_use":
                            self.log("sub" if sub else "tool", describe_tool(item.get("name", ""), item.get("input")), stage)
                        elif item.get("type") == "text" and item.get("text", "").strip() and not sub:
                            self.log("note", one_line(item["text"])[:280], stage)
                elif event.get("type") == "result":
                    self.log("result", one_line(str(event.get("result") or ""))[:400] or "Session finished.", stage)
        code = self.proc.wait()
        self.proc = None
        return code

    # --- what's next ---

    def steps_next(self, branch, folder, steps, shared=False):
        """('run', branch, path), ('wait', text), ('again',) or None when every step is Done.

        Shared stages (units.md, pr-units.md and the final steps) can be seen by more than one
        driver. Each is claimed first, like a unit: the driver writes the file from its
        template with a 'Claimed by:' line and pushes it; only that driver runs the stage."""
        for step in steps:
            path = folder + "/" + step
            status = self.status_at(branch, path)
            if status == "Done":
                continue
            if status in WAITING:
                return ("wait", "{} is '{}' on {}".format(path, status, branch), branch, path)
            if shared:
                text = self.read_at(branch, path)
                if text is None:
                    self.claim_stage(branch, path)
                    return ("again",)
                claim = H.EMAIL.search(H.claim_of(text) or "")
                if claim and claim.group(0).lower() != self.email:
                    return ("wait", "{} on {}, which {}'s driver runs".format(path, branch, claim.group(0)))
            return ("run", branch, path)
        return None

    def claim_stage(self, branch, path):
        self.switch_to(branch)
        name = os.path.basename(path)
        template = "pr.md" if name.startswith("pr") else name
        replacements = []
        if name == "check-assessment.md":  # the final check always needs QA's approval
            replacements.append((r"^Approval needed:.*$", "Approval needed: yes"))
        self.from_template(template, path, replacements, claim=True)
        self.git("add", "-A", *NOT_OURS)
        self.git("commit", "-q", "-m", "AIDLC {}: claim {}".format(self.task, path))
        if self.git("push", "-q", check=False).returncode != 0:
            self.git("fetch", "-q", "origin")
            self.git("reset", "-q", "--hard", "origin/" + branch)
            if self.read_at(branch, path) is None:
                raise Stop("couldn't push the claim for {} to {}, and nobody else claimed it. "
                           "Check push access to that branch.".format(path, branch))
            self.say("{} was claimed by another driver first".format(path))
            return
        self.say("claimed {}".format(path))

    def claimed_by_me(self, path):
        m = H.EMAIL.search(H.claim_of(H.read_text(os.path.join(self.root, path))) or "")
        return m is None or m.group(0).lower() == self.email

    def feature_next(self):
        branch = "feature/" + self.task
        if not self.remote_has(branch):
            if not self.args.request:
                raise Stop("there is no branch {} yet. To start new work, give the request: "
                           "aidlc_driver.py {} \"<request or ClickUp link>\"".format(branch, self.task), notify=False)
            self.switch_to(branch, create_from=self.target)
            self.write_clarify(self.folder, self.args.request)
            self.commit_and_push("AIDLC {}: claim".format(self.task))
            return ("again",)
        claim = self.claim_at(branch, self.folder)
        if claim and claim != self.email:
            raise Stop("{} is claimed by {}. Only their driver runs it.".format(self.task, claim), notify=False)
        return self.steps_next(branch, self.folder, SMALL_STEPS) or \
            ("done", "Every step is Done and the PR is open. A person reviews and merges it.")

    def project_next(self):
        units_path = self.folder + "/units.md"
        if self.status_at(self.target, units_path) != "Done":
            branch = "feature/" + self.task
            if not self.remote_has(branch):
                if not self.args.tdd:
                    raise Stop("units.md isn't on {} yet. Start a project or new module with: aidlc_driver.py {} --tdd "
                               "\"<approved TDD copy link>\"".format(self.target, self.task), notify=False)
                self.switch_to(branch, create_from=self.target)
                self.from_template("units.md", units_path, [
                    (r"^# Units: .*$", "# Units: " + self.task),
                    (r"^\| Task \|.*$", "| Task | {} |".format(self.task)),
                    (r"^\| Approved TDD copy \|.*$", "| Approved TDD copy | {} |".format(one_line(self.args.tdd))),
                ], claim=True)
                self.commit_and_push("AIDLC {}: start units.md".format(self.task))
                return ("again",)
            return self.steps_next(branch, self.folder, ["units.md", "pr-units.md"], shared=True) or \
                ("wait", "the units.md PR ({} into {}) to be merged".format(branch, self.target))

        modules = parse_units(self.read_at(self.target, units_path))
        merged = {m["name"] for m in modules
                  if self.status_at(self.target, "{}/{}/pr.md".format(self.folder, m["name"])) == "Done"}
        if len(merged) == len(modules):
            branch = "feature/{}-final".format(self.task)
            if not self.remote_has(branch):
                self.switch_to(branch, create_from=self.target)
                return ("again",)
            return self.steps_next(branch, self.folder, FINAL_STEPS, shared=True) or \
                ("done", "The final check is approved and the final PR is open. A person reviews and merges it.")
        # A driver finishes the module it owns (up to its open PR) before it takes another one,
        # so a second person's driver can take the other modules.
        own_wait = None
        for m in modules:
            if m["name"] in merged or self.owner(m) != self.email:
                continue
            if self.status_at(self.module_branch(m), "{}/{}/pr.md".format(self.folder, m["name"])) == "Done":
                continue
            action = self.module_next(m)
            if action[0] != "wait":
                return action
            own_wait = own_wait or action
        if own_wait:
            return own_wait
        first_wait = None
        for m in modules:
            if m["name"] in merged or any(dep not in merged for dep in m["depends"]):
                continue
            action = self.module_next(m)
            if action[0] != "wait":
                return action
            first_wait = first_wait or action
        return first_wait or ("wait", "modules this work depends on to be merged into " + self.target)

    def module_branch(self, m):
        return "feature/{}-{}".format(self.task, m["name"])

    def owner(self, m):
        branch = self.module_branch(m)
        if not self.remote_has(branch):
            return None
        for phase in m["phases"]:
            for u in phase["units"]:
                claim = self.claim_at(branch, self.folder + "/" + u["folder"])
                if claim:
                    return claim
        return None

    def module_next(self, m):
        """A module runs on its own branch, its units one after another, by one person's driver:
        whoever claimed its first unit."""
        branch = self.module_branch(m)
        if not self.remote_has(branch):
            self.switch_to(branch, create_from=self.target)
            return ("again",)
        base = self.folder + "/"
        owner = self.owner(m)
        if owner and owner != self.email:
            return ("wait", "module {}, which {}'s driver runs".format(m["name"], owner))
        for phase in m["phases"]:
            for u in phase["units"]:
                folder = base + u["folder"]
                if self.status_at(branch, folder + "/learnings.md") == "Done":
                    continue
                if self.claim_at(branch, folder) is None:
                    self.claim(m, phase, u, branch)
                    return ("again",)
                return self.steps_next(branch, folder, UNIT_STEPS) or ("again",)
            phase_dir = os.path.dirname(phase["units"][0]["folder"])
            action = self.steps_next(branch, base + phase_dir, ["phase-check.md"])
            if action is not None:
                return action
        return self.steps_next(branch, base + m["name"], ["pr.md"]) or \
            ("wait", "the {} PR ({} into {}) to be merged".format(m["name"], branch, self.target))

    def claim(self, m, phase, u, module_branch):
        """Item 26: claim by a committed and pushed line before any work starts."""
        self.switch_to(module_branch)
        folder = self.folder + "/" + u["folder"]
        self.write_clarify(folder, "units.md: {}, {}, {}: {}".format(m["name"], phase["title"], u["id"], u["behavior"]))
        self.git("add", "-A", *NOT_OURS)
        self.git("commit", "-q", "-m", "AIDLC {}: claim {} {}".format(self.task, m["name"], u["id"]))
        if self.git("push", "-q", check=False).returncode != 0:
            self.git("fetch", "-q", "origin")
            self.git("reset", "-q", "--hard", "origin/" + module_branch)
            if self.claim_at(module_branch, folder) is None:
                raise Stop("couldn't push the claim for {} {} to {}, and nobody else claimed it. "
                           "Check push access to that branch.".format(m["name"], u["id"], module_branch))
            self.say("{} {} was claimed by another driver first".format(m["name"], u["id"]))
            return
        self.say("claimed {} {}".format(m["name"], u["id"]))

    def next_action(self):
        self.git("fetch", "-q", "--prune", "origin")
        units = self.folder + "/units.md"
        project = bool(self.args.tdd) or self.read_at(self.target, units) is not None or \
            (self.remote_has("feature/" + self.task) and self.read_at("feature/" + self.task, units) is not None)
        self.is_project = project
        return self.project_next() if project else self.feature_next()

    # --- the loop ---

    def run(self):
        """The loop. The git lock is held while it works and released while it waits, so the page can
        record answers and approvals then."""
        while not self.stopping.is_set():
            with self.lock:
                action = self.next_action()
                kind = action[0]
                if kind == "run":
                    self.last_wait = None
                    self.run_stage(action[1], action[2])
                    continue
                if kind == "wait":
                    self.wake.clear()  # before the page can act, so its wake-up is never lost
                    self.phase, self.current = "waiting", None
                    self.waiting = {"text": action[1], "branch": action[2] if len(action) > 2 else None,
                                    "path": action[3] if len(action) > 3 else None}
                    if action[1] != self.last_wait:
                        self.say("waiting on {}.".format(action[1]))
                        self.last_wait = action[1]
                    if self.waiting["path"]:
                        self.tell_waiting(self.waiting["branch"], self.waiting["path"])
            if kind == "again":
                continue
            if kind == "wait":
                self.wake.wait(self.args.wait_minutes * 60)
            elif kind == "done":
                self.phase, self.waiting, self.message = "done", None, action[1]
                self.say(action[1])
                return 0
        raise Stopped()

    # --- stopping when the Claude Code window closes ---

    def watch(self, pid):
        """Stop when the process `pid` (the Claude Code window that started the driver) is gone."""
        def alive():
            try:
                os.kill(pid, 0)
                return True
            except ProcessLookupError:
                return False
            except PermissionError:
                return True

        def loop():
            while alive():
                time.sleep(2)
            self.stopping.set()
            self.wake.set()
            self.end_session()
        threading.Thread(target=loop, daemon=True).start()

    def end_session(self):
        """Stop the running session (and anything it started): politely, then for sure."""
        proc = self.proc
        if not proc or proc.poll() is not None:
            return
        for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
            try:
                os.killpg(proc.pid, sig)
            except OSError:
                return
            try:
                proc.wait(timeout=wait)
                return
            except subprocess.TimeoutExpired:
                continue

    def discard_half_done(self):
        """Throw away what a cut-off step left behind: back to the last commit."""
        self.git("reset", "-q", "--hard", "HEAD", check=False)
        self.git("clean", "-q", "-fd", "-e", ".claude/settings.local.json", check=False)

    def write_state(self):
        git_dir = self.git_out("rev-parse", "--absolute-git-dir")
        with open(os.path.join(git_dir, STATE_FILE), "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "task": self.task, "url": self.page.url if self.page else None,
                       "started": self.started}, f)

    def clear_state(self):
        try:
            os.remove(os.path.join(self.git_out("rev-parse", "--absolute-git-dir"), STATE_FILE))
        except OSError:
            pass


def recover_cut_off(root):
    """If an earlier driver was killed while a step ran (no chance to clean up), stop that step's
    session if it still runs and throw its half-done changes away, as closing the window should."""
    git_dir = subprocess.run(["git", "-C", root, "rev-parse", "--absolute-git-dir"], capture_output=True,
                             text=True).stdout.strip()
    marker = os.path.join(git_dir, H.STAGE_MARKER)
    state = os.path.join(git_dir, STATE_FILE)
    if not os.path.exists(marker):
        return False
    try:
        with open(state, encoding="utf-8") as f:
            pid = json.load(f).get("pid")
        os.kill(pid, 0)
        return False  # its driver is still running
    except (OSError, ValueError, TypeError):
        pass
    text = H.read_text(marker) or ""
    m = re.search(r"session pid (\d+)", text)
    if m:
        try:
            os.killpg(int(m.group(1)), signal.SIGKILL)
        except OSError:
            pass
    subprocess.run(["git", "-C", root, "reset", "-q", "--hard", "HEAD"])
    subprocess.run(["git", "-C", root, "clean", "-q", "-fd", "-e", ".claude/settings.local.json"])
    for f in (marker, state):
        try:
            os.remove(f)
        except OSError:
            pass
    return True


def find_claude_ancestor():
    """The nearest parent process that is Claude Code, or None."""
    pid = os.getppid()
    for _ in range(12):
        if pid <= 1:
            return None
        out = subprocess.run(["ps", "-o", "ppid=,comm=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
        if not out:
            return None
        ppid, comm = out.split(None, 1) if " " in out else (out, "")
        if "claude" in os.path.basename(comm.strip()).lower():
            return pid
        pid = int(ppid)
    return None

def main():
    parser = argparse.ArgumentParser(description="AIDLC driver: one fresh headless session per stage.")
    parser.add_argument("task", help="the task name (short, lowercase, words joined by -)")
    parser.add_argument("request", nargs="?", help="for a new feature or bug fix: the request or ClickUp link")
    parser.add_argument("--tdd", help="for a project or new module: the link to the approved TDD copy")
    parser.add_argument("--wait-minutes", type=float, default=3, help="how often to check while waiting (default 3)")
    parser.add_argument("--claude", default="claude", help="the claude command (default: claude)")
    parser.add_argument("--approved", action="store_true",
                        help="the person already approved commits and pushes (asked by /aidlc:start)")
    parser.add_argument("--watch-pid", type=int, default=0,
                        help="stop when this process ends (the Claude Code window); default: the Claude Code "
                             "process this was started from, if any")
    parser.add_argument("--port", type=int, default=0, help="port for the page (default: any free port)")
    args = parser.parse_args()
    if not TASK_NAME.match(args.task):
        print("The task name must be lowercase letters and numbers, words joined by -.", file=sys.stderr)
        return 1
    if args.request and args.tdd:
        print("Give either a request (feature or bug fix) or --tdd (project or new module), not both.", file=sys.stderr)
        return 1
    driver = None
    watch_pid = args.watch_pid or find_claude_ancestor()
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
        recovered = bool(top) and recover_cut_off(top)
        driver = Driver(args)
        if recovered:
            driver.say("an earlier run was cut off in the middle of a step; its half-done changes were thrown away.")

        def on_signal(signum, frame):
            driver.stopping.set()
            driver.wake.set()
            driver.end_session()
        for sig in (signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, on_signal)
        if driver.git_out("status", "--porcelain", *NOT_OURS):
            raise Stop("the working tree has uncommitted changes. Commit or stash them first.", notify=False)
        if not args.approved:
            answer = input("AI will commit and push to this work's own branches (feature/...) for '{}'. "
                           "It never pushes to {}. Approve? [y/N] ".format(args.task, driver.target))
            if answer.strip().lower() not in ("y", "yes"):
                print("Not approved. Nothing was done.")
                return 1
        driver.page = aidlc_page.Page(driver)
        url = driver.page.start()
        print("AIDLC page: " + url, flush=True)
        driver.write_state()
        if watch_pid:
            driver.watch(watch_pid)
        code = driver.run()
        # Done: keep the page up until the window closes (or until Ctrl+C from a terminal).
        while watch_pid and not driver.stopping.is_set():
            driver.stopping.wait(5)
        return code
    except Stopped:
        if driver is not None:
            if driver.cut_off:
                driver.discard_half_done()
                marker = os.path.join(driver.git_out("rev-parse", "--absolute-git-dir"), H.STAGE_MARKER)
                if os.path.exists(marker):
                    os.remove(marker)
            driver.say("the Claude Code window closed, so the work stopped. Run /aidlc:start to continue.")
        return 0
    except Stop as stop:
        print("AIDLC driver stopped: {}".format(stop), file=sys.stderr)
        if driver is not None:
            driver.phase, driver.message = "stopped", str(stop)
            driver.log("driver", "Stopped: " + str(stop))
            if stop.notify:
                driver.notify("the driver stopped. " + str(stop))
            # Keep the page up so the developer can read why, until the window closes.
            while watch_pid and driver.page and not driver.stopping.is_set():
                driver.stopping.wait(5)
        return 1
    except (KeyboardInterrupt, EOFError):
        if driver is not None and driver.proc and driver.proc.poll() is None:
            driver.end_session()
            driver.discard_half_done()
        print("\nAIDLC driver stopped. Run the same command again to continue.")
        return 1
    finally:
        if driver is not None:
            driver.clear_state()
            if driver.page:
                driver.page.stop()


if __name__ == "__main__":
    sys.exit(main())
