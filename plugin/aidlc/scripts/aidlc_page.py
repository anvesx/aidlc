#!/usr/bin/env python3
"""The AIDLC page: a local web page for one driver run.

The driver starts this on 127.0.0.1 (this laptop only). The page shows the work's steps and
their status, what the running session is doing, and what each step wrote. When something
waits on the developer, they answer, approve or say no on the page; this file records it in
the step's file under their git name (approvals exactly as /aidlc:approve does), commits and
pushes, and wakes the driver. The AI never calls this: only a click on the page does.

Every request needs the random token in the page link. There is no sign-in yet: being on the
developer's laptop is the proof that it's them. Standard library only.
"""

import datetime
import json
import os
import re
import secrets
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import aidlc_hooks as H

PAGE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "page", "index.html")
STEP_LABELS = {
    "clarify.md": "Clarify", "plan.md": "Plan", "build-log.md": "Build", "check-assessment.md": "Check",
    "learnings.md": "Record", "pr.md": "PR", "units.md": "Split into units", "pr-units.md": "units.md PR",
    "phase-check.md": "Phase check", "pr-final.md": "Last PR",
}


KNOWN = set(H.STATUSES) | {"Running", "Not started"}


# ---------- reading the work ----------

def split_row(line):
    """The cells of a markdown table row; '\\|' inside a cell stays in the cell."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", body)]


def join_row(cells):
    return "| " + " | ".join(cells) + " |"


def question_key(cells):
    return "{}|{}".format(cells.get("#", ""), next((v for k, v in cells.items() if "question" in k.lower()), ""))

def question_rows(text):
    """Open questions in a file: rows of a "Questions and answers" table (header with '#', 'Question'
    and 'Answer' columns) whose answer is empty. Returns [{line, cells, answer_col}] (line is 0-based in the file)."""
    rows, header, answer_col = [], None, None
    for i, line in enumerate((text or "").split("\n")):
        stripped = line.strip()
        if not stripped.startswith("|"):
            header, answer_col = None, None
            continue
        cells = split_row(stripped)
        if header is None:
            low = [c.lower() for c in cells]
            if "#" in low and any("question" in c for c in low) and "answer" in low:
                header, answer_col = cells, low.index("answer")
            else:
                header = []
            continue
        if not header or all(set(c) <= set("-: ") for c in cells):
            continue
        while len(cells) < len(header):
            cells.append("")
        if not cells[answer_col]:
            shown = {header[j]: cells[j] for j in range(len(header)) if j != answer_col}
            rows.append({"line": i, "answer_col": answer_col, "cells": shown, "key": question_key(shown)})
    return rows


def section(text, title):
    m = re.search(r"^##+\s*" + re.escape(title) + r"[^\n]*\n(.*?)(?=^##\s|\Z)", text or "", re.M | re.S | re.I)
    return m.group(1).strip() if m else ""


class Page:
    def __init__(self, driver):
        self.d = driver
        self.token = secrets.token_urlsafe(18)
        self.server = None
        self.url = None
        self._groups = (0, None, None)  # (time, signature, groups): git is read at most every few seconds

    # --- state ---

    def item(self, branch, path, label=None):
        status = None
        if branch and self.d.remote_has(branch):
            status = self.d.status_at(branch, path)
        running = self.d.current and self.d.current.get("path") == path and self.d.current.get("branch") == branch
        shown = "Running" if running else (status or "Not started")
        return {"path": path, "branch": branch, "label": label or STEP_LABELS.get(os.path.basename(path), path),
                "status": shown if shown in KNOWN else "Unknown"}

    def groups(self):
        d, folder = self.d, self.d.folder
        if not d.is_project:
            branch = "feature/" + d.task
            return [{"title": "Steps", "items": [self.item(branch, folder + "/" + s) for s in d.feature_steps]}]
        units_branch = d.target if d.status_at(d.target, folder + "/units.md") == "Done" else "feature/" + d.task
        groups = [{"title": "Split into units", "items": [
            self.item(units_branch, folder + "/units.md"), self.item(units_branch, folder + "/pr-units.md")]}]
        text = d.read_at(units_branch, folder + "/units.md")
        try:
            modules = d.parse_units(text) if text and d.status_at(units_branch, folder + "/units.md") in ("Approved", "Done") else []
        except Exception:
            modules = []
        for m in modules:
            branch = d.module_branch(m)
            phases = []
            for phase in m["phases"]:
                units = [{"id": u["id"], "behavior": u["behavior"],
                          "steps": [self.item(branch, folder + "/" + u["folder"] + "/" + s,
                                              "{} {}".format(u["id"], STEP_LABELS[s])) for s in d.unit_steps]}
                         for u in phase["units"]]
                check = folder + "/" + os.path.dirname(phase["units"][0]["folder"]) + "/phase-check.md"
                phases.append({"title": phase["title"], "units": units, "check": self.item(branch, check)})
            groups.append({"title": "Module " + m["name"], "branch": branch, "owner": d.owner(m),
                           "phases": phases, "items": [self.item(branch, folder + "/" + m["name"] + "/pr.md", "Module PR")]})
        final = "feature/{}-final".format(d.task)
        groups.append({"title": "The whole", "items": [self.item(final, folder + "/" + s) for s in d.final_steps]})
        return groups

    def needs_you(self):
        w = self.d.waiting
        if not w or not w.get("path"):
            return None
        branch, path = w["branch"], w["path"]
        text = self.d.read_at(branch, path) or ""
        status = H.status_of(text)
        if status not in ("Waiting for answers", "Waiting for approval", "Waiting for go-back approval"):
            return None
        kind = {"Waiting for answers": "answers", "Waiting for approval": "approval",
                "Waiting for go-back approval": "goback"}[status]
        people = self.d.people_for(branch, path)
        return {"branch": branch, "path": path, "kind": kind, "status": status,
                "mine": self.mine(branch, path, people), "who": [p.get("name") or p.get("email") for p in people],
                "label": STEP_LABELS.get(os.path.basename(path), path),
                "questions": question_rows(text) if kind == "answers" else [],
                "note": section(text, "Waiting on a person") or section(text, "Why go back")
                or section(text, "Failure and cause"),
                "text": text}

    def mine(self, branch, path, people=None):
        people = people if people is not None else self.d.people_for(branch, path)
        return any(p.get("email") == self.d.email for p in people)

    def cached_groups(self):
        d = self.d
        sig = (d.phase, (d.current or {}).get("path"), (d.waiting or {}).get("text"), d.seq if d.phase == "starting" else 0)
        at, old_sig, groups = self._groups
        if groups is None or old_sig != sig or time.time() - at > 4:
            groups = self.groups()
            self._groups = (time.time(), sig, groups)
        return groups

    def state(self):
        d = self.d
        return {
            "task": d.task, "request": d.request_text(), "kind": "project" if d.is_project else "feature",
            "target": d.target, "person": {"name": d.name, "email": d.email},
            "driver": {"state": d.phase, "message": d.message, "current": d.current,
                       "waiting": d.waiting, "started": d.started, "now": datetime.datetime.now().astimezone().isoformat(timespec="seconds")},
            "groups": self.cached_groups(), "needs_you": self.needs_you(),
            "activity": list(d.activity),
        }

    def file(self, branch, path):
        if self.d.current and self.d.current.get("path") == path:
            text = H.read_text(os.path.join(self.d.root, path))
            if text is not None:
                return text
        return self.d.read_at(branch, path) or ""

    # --- actions (all under the driver's git lock) ---

    def act(self, body):
        action, branch, path = body.get("action"), body.get("branch"), body.get("path")
        w = self.d.waiting or {}
        if not path or path != w.get("path") or branch != w.get("branch"):
            return 409, {"ok": False, "message": "That item isn't waiting any more. The page will refresh."}
        if not self.mine(branch, path):
            return 403, {"ok": False, "message": "This step waits on someone else; they answer in their own session."}
        if not self.d.lock.acquire(timeout=10):
            return 409, {"ok": False, "message": "The driver is busy right now. Try again in a moment."}
        try:
            self.d.switch_to(branch)
            full = os.path.join(self.d.root, path)
            text = H.read_text(full) or ""
            status = H.status_of(text)
            if action == "approve":
                if status not in ("Waiting for approval", "Waiting for go-back approval"):
                    return 409, {"ok": False, "message": "It isn't waiting for approval any more."}
                ok, message = H.record_approval(self.d.root, full, status)
                if ok:
                    self.d.log("you", "You approved " + STEP_LABELS.get(os.path.basename(path), path))
                return (200 if ok else 403), {"ok": ok, "message": message}
            if action not in ("answer", "decline"):
                return 400, {"ok": False, "message": "Unknown action."}
            today = datetime.date.today().isoformat()
            who = "{} on {}".format(self.d.name, today)
            if action == "answer":
                if status != "Waiting for answers":
                    return 409, {"ok": False, "message": "It isn't waiting for answers any more."}
                answers = {str(k): str(v).strip() for k, v in (body.get("answers") or {}).items() if str(v).strip()}
                free = (body.get("text") or "").strip()
                if not answers and not free:
                    return 400, {"ok": False, "message": "Write at least one answer."}
                lines = text.split("\n")
                found = 0
                for row in question_rows(text):  # matched by question, not line, in case the file moved
                    if row["key"] in answers:
                        cells = split_row(lines[row["line"]])
                        while len(cells) <= row["answer_col"]:
                            cells.append("")
                        cells[row["answer_col"]] = answers[row["key"]].replace("|", "/").replace("\n", " ")
                        lines[row["line"]] = join_row(cells)
                        found += 1
                if answers and not found:
                    return 409, {"ok": False, "message": "Those questions changed. The page will refresh."}
                text = "\n".join(lines)
                if free:
                    text = text.rstrip("\n") + "\n\n## Answer from {}\n{}\n".format(who, free)
                message = "AIDLC answers: " + path
                self.d.log("you", "You answered " + STEP_LABELS.get(os.path.basename(path), path))
            else:
                if status not in ("Waiting for approval", "Waiting for go-back approval"):
                    return 409, {"ok": False, "message": "It isn't waiting for approval any more."}
                reason = (body.get("text") or "").strip()
                if not reason:
                    return 400, {"ok": False, "message": "Say why, so the next session knows what to change."}
                text = text.rstrip("\n") + "\n\n## Not approved ({})\n{}\n".format(who, reason)
                message = "AIDLC not approved: " + path
                self.d.log("you", "You said no to " + STEP_LABELS.get(os.path.basename(path), path))
            text = H.STATUS_LINE.sub("Status: Draft", text, count=1)
            with open(full, "w", encoding="utf-8") as f:
                f.write(text)
            self.d.git("add", "--", path)
            self.d.git("commit", "-q", "-m", message, "--", path)
            error = H.push(self.d.root)
            if error:
                return 500, {"ok": False, "message": "Saved and committed, but not pushed: " + error}
            return 200, {"ok": True, "message": "Saved. The work carries on."}
        except Exception as e:  # report, don't crash the page
            return 500, {"ok": False, "message": "Something went wrong: {}".format(e)}
        finally:
            self.d.lock.release()
            self.d.wake.set()

    # --- server ---

    def start(self):
        page = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send(self, code, body, ctype="application/json"):
                data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype + "; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def allowed(self, query):
                given = (query.get("t") or [""])[0] or self.headers.get("X-AIDLC-Token", "")
                try:
                    return secrets.compare_digest(given.encode("utf-8"), page.token.encode("utf-8"))
                except (TypeError, ValueError):
                    return False

            def do_GET(self):
                url = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(url.query)
                if not self.allowed(query):
                    return self.send(403, b"This link needs its token. Use the link AIDLC gave you.", "text/plain")
                if url.path in ("/", "/index.html"):
                    try:
                        with open(PAGE_FILE, "rb") as f:
                            return self.send(200, f.read(), "text/html")
                    except OSError:
                        return self.send(500, b"page/index.html is missing from the plugin.", "text/plain")
                if url.path == "/api/state":
                    return self.send(200, page.state())
                if url.path == "/api/file":
                    branch = (query.get("branch") or [""])[0]
                    path = (query.get("path") or [""])[0]
                    if not path.startswith(page.d.folder + "/"):
                        return self.send(400, {"ok": False})
                    return self.send(200, {"text": page.file(branch, path)})
                return self.send(404, {"ok": False})

            def do_POST(self):
                url = urllib.parse.urlparse(self.path)
                if not self.allowed(urllib.parse.parse_qs(url.query)) or url.path != "/api/act":
                    return self.send(403, {"ok": False, "message": "Not allowed."})
                try:
                    body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0") or 0)) or b"{}")
                except ValueError:
                    return self.send(400, {"ok": False, "message": "Bad request."})
                code, result = page.act(body)
                return self.send(code, result)

        self.server = ThreadingHTTPServer(("127.0.0.1", self.d.args.port), Handler)
        self.server.daemon_threads = True
        self.url = "http://127.0.0.1:{}/?t={}".format(self.server.server_address[1], self.token)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self.url

    def stop(self):
        if self.server:
            self.server.shutdown()
