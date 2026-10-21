#!/usr/bin/env python3
"""Tests for aidlc_hooks.py. Run: python3 -m unittest test_aidlc_hooks -v  (from this folder)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aidlc_hooks.py")


def run(event, data, cwd, driver=False):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=cwd, CLAUDE_PLUGIN_ROOT="/plugins/aidlc")
    env.pop("AIDLC_DRIVER", None)
    if driver:
        env["AIDLC_DRIVER"] = "1"
    p = subprocess.run([sys.executable, HOOKS, event], input=json.dumps(data),
                       capture_output=True, text=True, env=env, cwd=cwd)
    return p.returncode, p.stdout, p.stderr


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def step(status, approval="no", body="body\n", claim=None):
    claim_line = "Claimed by: {}\n".format(claim) if claim else ""
    return "Status: {}\nApproval needed: {}\n{}\n# Step\n{}".format(status, approval, claim_line, body)


ME = "Test Person <test@example.com> on 2026-10-21"
PROJECT = """# Project: demo

## AIDLC
- Target branch: main

## Team

| Name | Git email | Slack user ID | Role |
|---|---|---|---|
| Test Person | test@example.com | U001 | Developer |
| Tina Lead | lead@example.com | U002 | Tech lead |
| Quinn QA | qa@example.com | U003 | QA |

## What it is
"""


def git(root, *args):
    return subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True, check=True).stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "repo")
        self.remote = os.path.join(self.tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", self.remote], check=True)
        subprocess.run(["git", "init", "-q", self.root], check=True)
        self.set_identity("Test Person", "test@example.com")
        git(self.root, "config", "core.autocrlf", "false")
        os.makedirs(os.path.join(self.root, "aidlc", "work"))
        write(os.path.join(self.root, "aidlc", "index.md"), "# AIDLC index\n")
        write(os.path.join(self.root, "aidlc", "project.md"), PROJECT)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "init")
        git(self.root, "remote", "add", "origin", self.remote)
        git(self.root, "switch", "-q", "-c", "feature/demo")
        git(self.root, "push", "-q", "-u", "origin", "feature/demo")
        self.work = os.path.join(self.root, "aidlc", "work", "demo")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def set_identity(self, name, email):
        git(self.root, "config", "user.name", name)
        git(self.root, "config", "user.email", email)

    def remote_log(self):
        return subprocess.run(["git", "--git-dir", self.remote, "log", "--format=%an|%s", "feature/demo"],
                              capture_output=True, text=True).stdout

    def p(self, *parts):
        return os.path.join(self.root, *parts)

    def guard(self, tool, tool_input):
        return run("guard", {"tool_name": tool, "tool_input": tool_input, "cwd": self.root}, self.root)


class SessionStart(Base):
    def test_loads_index_and_open_work(self):
        write(os.path.join(self.work, "clarify.md"), step("Waiting for approval"))
        code, out, _ = run("session-start", {"cwd": self.root}, self.root)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(code, 0)
        self.assertIn("# AIDLC index", ctx)
        self.assertIn("clarify.md: Waiting for approval", ctx)
        self.assertIn("/plugins/aidlc/scripts/aidlc_driver.py", ctx)
        self.assertIn("person's own session", ctx)

    def test_driver_session_is_named(self):
        _, out, _ = run("session-start", {"cwd": self.root}, self.root, driver=True)
        self.assertIn("This is a driver session", json.loads(out)["hookSpecificOutput"]["additionalContext"])

    def test_not_set_up(self):
        shutil.rmtree(self.p("aidlc"))
        _, out, _ = run("session-start", {"cwd": self.root}, self.root)
        self.assertIn("not set up", out)


class GuardCode(Base):
    def test_code_blocked_without_finished_plan(self):
        code, _, err = self.guard("Write", {"file_path": self.p("src", "a.js"), "content": "x"})
        self.assertEqual(code, 2)
        self.assertIn("finished plan", err)

    def test_code_allowed_with_finished_plan(self):
        write(os.path.join(self.work, "plan.md"), step("Done"))
        code, _, _ = self.guard("Write", {"file_path": self.p("src", "a.js"), "content": "x"})
        self.assertEqual(code, 0)

    def test_code_blocked_once_check_is_done(self):
        write(os.path.join(self.work, "plan.md"), step("Done"))
        write(os.path.join(self.work, "check-assessment.md"), step("Done"))
        code, _, _ = self.guard("Write", {"file_path": self.p("src", "a.js"), "content": "x"})
        self.assertEqual(code, 2)

    def test_aidlc_files_and_claude_md_always_allowed(self):
        for f in (self.p("aidlc", "index.md"), self.p("CLAUDE.md")):
            code, _, _ = self.guard("Write", {"file_path": f, "content": "x"})
            self.assertEqual(code, 0, f)


class GuardApprovals(Base):
    def test_ai_cannot_write_approval_line(self):
        f = os.path.join(self.work, "clarify.md")
        write(f, step("Draft"))
        code, _, err = self.guard("Edit", {"file_path": f, "old_string": "body", "new_string": "Approved by: Me"})
        self.assertEqual(code, 2)
        self.assertIn("only the person can approve", err)

    def test_template_placeholder_is_fine(self):
        code, _, _ = self.guard("Write", {"file_path": self.p("aidlc", "prd.md"),
                                          "content": "Approved by: <name>   Date: <date>"})
        self.assertEqual(code, 0)

    def test_keeping_an_existing_approval_line_is_fine(self):
        f = os.path.join(self.work, "plan.md")
        write(f, step("Waiting for approval") + "\nApproved by: Old <o@x> on 2026-01-01\n")
        code, _, _ = self.guard("Edit", {"file_path": f, "old_string": "body", "new_string": "body two"})
        self.assertEqual(code, 0)

    def test_done_needs_approval_when_approval_needed(self):
        f = os.path.join(self.work, "clarify.md")
        write(f, step("Draft", "yes"))
        code, _, err = self.guard("Edit", {"file_path": f, "old_string": "Status: Draft", "new_string": "Status: Done"})
        self.assertEqual(code, 2)
        self.assertIn("needs the person's approval", err)

    def test_done_without_approval_when_not_needed(self):
        f = os.path.join(self.work, "clarify.md")
        write(f, step("Draft", "no"))
        code, _, _ = self.guard("Edit", {"file_path": f, "old_string": "Status: Draft", "new_string": "Status: Done"})
        self.assertEqual(code, 0)

    def test_cannot_turn_approval_needed_off(self):
        f = os.path.join(self.work, "check-assessment.md")
        write(f, step("Draft", "yes"))
        code, _, _ = self.guard("Edit", {"file_path": f, "old_string": "Approval needed: yes",
                                         "new_string": "Approval needed: no"})
        self.assertEqual(code, 2)

    def test_bash_approval_blocked_but_grep_allowed(self):
        code, _, _ = self.guard("Bash", {"command": "echo 'Approved by: Someone' >> aidlc/work/x/plan.md"})
        self.assertEqual(code, 2)
        code, _, _ = self.guard("Bash", {"command": "echo Approved by: Someone Else >> plan.md"})
        self.assertEqual(code, 2)
        code, _, _ = self.guard("Bash", {"command": "grep -n \"Approved by:\" aidlc/work/x/plan.md"})
        self.assertEqual(code, 0)

    def test_google_doc_approval_blocked(self):
        code, _, _ = self.guard("mcp__Google_Docs__update_doc",
                                {"requests": [{"insertText": {"text": "Approved by: Aditya   Date: 2026-10-20"}}]})
        self.assertEqual(code, 2)
        code, _, _ = self.guard("mcp__Google_Docs__update_doc",
                                {"requests": [{"insertText": {"text": "Approved by: <name>   Date: <date>"}}]})
        self.assertEqual(code, 0)


class GuardDoneAndDecisions(Base):
    def test_done_file_cannot_be_edited(self):
        f = os.path.join(self.work, "plan.md")
        write(f, step("Done"))
        code, _, err = self.guard("Edit", {"file_path": f, "old_string": "body", "new_string": "changed"})
        self.assertEqual(code, 2)
        self.assertIn("is Done", err)

    def test_done_file_can_only_be_marked_stale(self):
        f = os.path.join(self.work, "plan.md")
        write(f, step("Done"))
        code, _, _ = self.guard("Edit", {"file_path": f, "old_string": "Status: Done", "new_string": "Status: Stale"})
        self.assertEqual(code, 0)
        code, _, _ = self.guard("Write", {"file_path": f, "content": step("Stale", body="sneaky change\n")})
        self.assertEqual(code, 2)

    def test_stale_file_can_be_redone(self):
        f = os.path.join(self.work, "plan.md")
        write(f, step("Stale"))
        code, _, _ = self.guard("Write", {"file_path": f, "content": step("Draft", body="redone\n")})
        self.assertEqual(code, 0)

    def test_active_decision_only_replaced(self):
        f = self.p("aidlc", "decisions", "D-001-x.md")
        write(f, "# D-001: x\n\nStatus: Active\n\n## Decision\nUse A.\n")
        code, _, _ = self.guard("Edit", {"file_path": f, "old_string": "Use A.", "new_string": "Use B."})
        self.assertEqual(code, 2)
        code, _, _ = self.guard("Edit", {"file_path": f, "old_string": "Status: Active",
                                         "new_string": "Status: Replaced by D-002"})
        self.assertEqual(code, 0)


class GuardUnitsAndClaims(Base):
    def test_ai_cannot_set_approved(self):
        f = os.path.join(self.work, "units.md")
        write(f, step("Draft", "yes"))
        code, _, err = self.guard("Edit", {"file_path": f, "old_string": "Status: Draft", "new_string": "Status: Approved"})
        self.assertEqual(code, 2)
        self.assertIn("only the approve hook", err)

    def test_approved_units_only_links_change(self):
        f = os.path.join(self.work, "units.md")
        write(f, step("Approved", "yes", body="| U1 | a | |\nPhase ticket: \n") + "\nApproved by: " + ME + "\n")
        code, _, _ = self.guard("Edit", {"file_path": f, "old_string": "| U1 | a | |",
                                         "new_string": "| U1 | a | https://app.clickup.com/t/abc |"})
        self.assertEqual(code, 0)
        code, _, _ = self.guard("Edit", {"file_path": f, "old_string": "| U1 | a | |", "new_string": "| U1 | b | |"})
        self.assertEqual(code, 2)
        code, _, _ = self.guard("Edit", {"file_path": f, "old_string": "Status: Approved", "new_string": "Status: Done"})
        self.assertEqual(code, 0)
        code, _, _ = self.guard("Edit", {"file_path": f, "old_string": "Status: Approved", "new_string": "Status: Draft"})
        self.assertEqual(code, 2)

    def test_markdown_ticket_links_allowed(self):
        f = os.path.join(self.work, "units.md")
        write(f, step("Approved", "yes", body="| U1 | a | |\n") + "\nApproved by: " + ME + "\n")
        code, _, _ = self.guard("Edit", {"file_path": f, "old_string": "| U1 | a | |",
                                         "new_string": "| U1 | a | [CU-1](https://app.clickup.com/t/abc) |"})
        self.assertEqual(code, 0)

    def test_old_approval_does_not_count_after_a_go_back(self):
        f = os.path.join(self.work, "plan.md")
        write(f, step("Stale", "yes") + "\nApproved by: " + ME + "\n")
        code, _, _ = self.guard("Edit", {"file_path": f, "old_string": "Status: Stale", "new_string": "Status: Draft"})
        self.assertEqual(code, 0)
        write(f, step("Draft", "yes", body="redone\n") + "\nApproved by: " + ME + "\n")
        code, _, err = self.guard("Edit", {"file_path": f, "old_string": "Status: Draft", "new_string": "Status: Done"})
        self.assertEqual(code, 2)
        self.assertIn("needs the person's approval", err)

    def test_driver_session_cannot_change_claude_settings(self):
        write(os.path.join(self.work, "plan.md"), step("Done"))
        f = self.p(".claude", "settings.json")
        data = {"tool_name": "Write", "tool_input": {"file_path": f, "content": "{}"}, "cwd": self.root}
        self.assertEqual(run("guard", data, self.root, driver=True)[0], 2)
        self.assertEqual(run("guard", data, self.root)[0], 0)

    def test_person_session_can_write_claude_settings_without_a_plan(self):
        f = self.p(".claude", "settings.json")
        data = {"tool_name": "Write", "tool_input": {"file_path": f, "content": "{}"}, "cwd": self.root}
        self.assertEqual(run("guard", data, self.root)[0], 0)
        self.assertEqual(run("guard", data, self.root, driver=True)[0], 2)

    def test_ai_cannot_call_the_page_actions(self):
        code, _, err = self.guard("Bash", {"command": "curl -X POST 'http://127.0.0.1:5000/api/act?t=abc' -d '{}'"})
        self.assertEqual(code, 2)
        self.assertIn("AIDLC page is for the person only", err)
        code, _, _ = self.guard("WebFetch", {"url": "http://127.0.0.1:5000/api/act?t=abc", "prompt": "x"})
        self.assertEqual(code, 2)
        code, _, _ = self.guard("Bash", {"command": "curl -s 'http://127.0.0.1:5000/api/state?t=abc'"})
        self.assertEqual(code, 0)

    def test_ai_cannot_write_code_that_approves(self):
        write(os.path.join(self.work, "plan.md"), step("Done"))
        code, _, _ = self.guard("Write", {"file_path": self.p("x.py"), "content": "import urllib; u='/api/act'"})
        self.assertEqual(code, 2)
        code, _, _ = self.guard("Write", {"file_path": self.p("y.py"), "content": "aidlc_hooks.record_approval(r, p, s)"})
        self.assertEqual(code, 2)
        code, _, _ = self.guard("Bash", {"command": "python3 -c 'import aidlc_hooks; aidlc_hooks.record_approval(1,2,3)'"})
        self.assertEqual(code, 2)
        code, _, _ = self.guard("Write", {"file_path": self.p("z.py"), "content": "print('ok')"})
        self.assertEqual(code, 0)

    def test_claim_line_cannot_change(self):
        f = os.path.join(self.work, "clarify.md")
        write(f, step("Draft", claim=ME))
        code, _, err = self.guard("Edit", {"file_path": f, "old_string": "test@example.com", "new_string": "x@example.com"})
        self.assertEqual(code, 2)
        self.assertIn("Claimed by", err)
        code, _, _ = self.guard("Edit", {"file_path": f, "old_string": "body", "new_string": "need"})
        self.assertEqual(code, 0)


class Approve(Base):
    def approve(self, prompt):
        code, out, _ = run("approve", {"prompt": prompt, "cwd": self.root}, self.root)
        self.assertEqual(code, 0)
        return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out.strip() else ""

    def claim(self, folder=None):
        write(os.path.join(folder or self.work, "clarify.md"), step("Done", claim=ME))

    def test_approves_the_one_waiting_file_commits_and_pushes(self):
        self.claim()
        f = os.path.join(self.work, "plan.md")
        write(f, step("Waiting for approval", "yes"))
        msg = self.approve("/aidlc:approve")
        text = read(f)
        self.assertIn("Status: Done", text)
        self.assertIn("Approved by: Test Person <test@example.com> on", text)
        self.assertIn("approved", msg)
        self.assertNotIn("not pushed", msg)
        self.assertIn("Test Person|AIDLC approve: aidlc/work/demo/plan.md", self.remote_log())

    def test_someone_else_cannot_approve_a_claimed_step(self):
        self.claim()
        f = os.path.join(self.work, "plan.md")
        write(f, step("Waiting for approval", "yes"))
        self.set_identity("Tina Lead", "lead@example.com")
        msg = self.approve("/aidlc:approve")
        self.assertIn("can only be approved by", msg)
        self.assertIn("Waiting for approval", read(f))

    def test_units_need_the_tech_lead_and_become_approved(self):
        f = os.path.join(self.work, "units.md")
        write(f, step("Waiting for approval", "yes"))
        self.assertIn("can only be approved by the tech lead", self.approve("/aidlc:approve"))
        self.set_identity("Tina Lead", "lead@example.com")
        self.approve("/aidlc:approve")
        self.assertIn("Status: Approved", read(f))
        self.assertIn("Approved by: Tina", read(f))

    def test_final_check_needs_qa(self):
        write(os.path.join(self.work, "units.md"), step("Done", "yes"))
        f = os.path.join(self.work, "check-assessment.md")
        write(f, step("Waiting for approval", "yes"))
        self.assertIn("can only be approved by QA", self.approve("/aidlc:approve"))
        self.set_identity("Quinn QA", "qa@example.com")
        self.approve("/aidlc:approve")
        self.assertIn("Status: Done", read(f))

    def test_phase_check_needs_a_developer_from_the_phase(self):
        phase = os.path.join(self.work, "cart", "phase-1-basics")
        self.claim(os.path.join(phase, "U1-add"))
        f = os.path.join(phase, "phase-check.md")
        write(f, step("Waiting for approval", "yes"))
        self.set_identity("Tina Lead", "lead@example.com")
        self.assertIn("a developer who claimed a unit", self.approve("/aidlc:approve"))
        self.set_identity("Test Person", "test@example.com")
        self.approve("/aidlc:approve")
        self.assertIn("Status: Done", read(f))

    def test_approver_must_be_in_the_team_table(self):
        write(os.path.join(self.work, "clarify.md"), step("Done", claim="Out Sider <out@example.com> on 2026-10-21"))
        f = os.path.join(self.work, "plan.md")
        write(f, step("Waiting for approval", "yes"))
        self.set_identity("Out Sider", "out@example.com")
        self.assertIn("can only be approved by", self.approve("/aidlc:approve"))

    def test_expanded_command_text_also_works(self):
        f = os.path.join(self.work, "clarify.md")
        write(f, step("Waiting for approval", "yes", claim=ME))
        self.approve("The person typed `/aidlc:approve `. The AIDLC approve hook has already handled it.")
        self.assertIn("Status: Done", read(f))

    def test_nothing_waiting(self):
        self.assertIn("nothing is waiting", self.approve("/approve"))

    def test_several_waiting_needs_a_choice(self):
        phase = os.path.join(self.work, "cart", "phase-1-basics")
        for unit in ("U1-a", "U2-b"):
            self.claim(os.path.join(phase, unit))
            write(os.path.join(phase, unit, "plan.md"), step("Waiting for approval", "yes"))
        self.assertIn("more than one", self.approve("/aidlc:approve"))
        self.approve("/aidlc:approve U2")
        self.assertIn("Status: Done", read(os.path.join(phase, "U2-b", "plan.md")))
        self.assertIn("Waiting for approval", read(os.path.join(phase, "U1-a", "plan.md")))

    def test_go_back_marks_target_and_later_steps_stale(self):
        self.claim()
        write(os.path.join(self.work, "plan.md"), step("Done"))
        write(os.path.join(self.work, "build-log.md"), step("Done"))
        write(os.path.join(self.work, "check-assessment.md"),
              step("Waiting for go-back approval", body="Go back to: plan.md\n\n## Why go back\nThe plan misses X.\n"))
        msg = self.approve("/aidlc:approve")
        self.assertIn("Status: Done", read(os.path.join(self.work, "clarify.md")))
        for name in ("plan.md", "build-log.md", "check-assessment.md"):
            self.assertIn("Status: Stale", read(os.path.join(self.work, name)), name)
        self.assertIn("Go-back approved by: Test Person", read(os.path.join(self.work, "check-assessment.md")))
        self.assertIn("going back to plan.md", msg)

    def test_pulls_before_approving(self):
        other = os.path.join(self.tmp, "other")
        subprocess.run(["git", "clone", "-q", "-b", "feature/demo", self.remote, other], check=True)
        git(other, "config", "user.name", "Driver")
        git(other, "config", "user.email", "test@example.com")
        self.claim(os.path.join(other, "aidlc", "work", "demo"))
        write(os.path.join(other, "aidlc", "work", "demo", "plan.md"), step("Waiting for approval", "yes"))
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "driver work")
        git(other, "push", "-q")
        self.approve("/aidlc:approve")
        self.assertIn("Status: Done", read(os.path.join(self.work, "plan.md")))

    def test_ordinary_message_is_ignored(self):
        write(os.path.join(self.work, "plan.md"), step("Waiting for approval", "yes"))
        self.assertEqual(self.approve("how does /aidlc:approve work?"), "")
        self.assertIn("Waiting for approval", read(os.path.join(self.work, "plan.md")))


class Stop(Base):
    def test_blocks_on_missing_status(self):
        write(os.path.join(self.work, "plan.md"), "# no status\n")
        _, out, _ = run("stop", {"cwd": self.root}, self.root)
        self.assertEqual(json.loads(out)["decision"], "block")

    def test_new_statuses_are_valid(self):
        write(os.path.join(self.work, "plan.md"), step("Waiting for answers"))
        write(os.path.join(self.work, "units.md"), step("Approved", "yes"))
        _, out, _ = run("stop", {"cwd": self.root}, self.root, driver=True)
        self.assertEqual(out.strip(), "")

    def test_person_session_commits_and_pushes_answers(self):
        write(os.path.join(self.work, "plan.md"), step("Draft", body="| 1 | Q | A | yes |\n"))
        _, out, _ = run("stop", {"cwd": self.root}, self.root)
        self.assertIn("committed and pushed", json.loads(out)["systemMessage"])
        self.assertIn("Test Person|AIDLC answers", self.remote_log())

    def test_no_commit_while_a_driver_stage_runs_here(self):
        git_dir = git(self.root, "rev-parse", "--absolute-git-dir").strip()
        write(os.path.join(git_dir, "aidlc-stage-running"), "x\n")
        write(os.path.join(self.work, "plan.md"), step("Draft"))
        _, out, _ = run("stop", {"cwd": self.root}, self.root)
        self.assertIn("running a stage", json.loads(out)["systemMessage"])
        self.assertNotIn("AIDLC answers", self.remote_log())

    def test_driver_session_does_not_commit(self):
        write(os.path.join(self.work, "plan.md"), step("Draft"))
        _, out, _ = run("stop", {"cwd": self.root}, self.root, driver=True)
        self.assertEqual(out.strip(), "")
        self.assertNotIn("AIDLC answers", self.remote_log())

    def test_no_commit_off_a_feature_branch(self):
        git(self.root, "switch", "-q", "-c", "main")
        write(os.path.join(self.work, "plan.md"), step("Draft"))
        _, out, _ = run("stop", {"cwd": self.root}, self.root)
        self.assertEqual(out.strip(), "")
        self.assertIn("aidlc/work", git(self.root, "status", "--porcelain"))

    def test_quiet_when_all_valid_or_already_stopping(self):
        write(os.path.join(self.work, "plan.md"), step("Draft"))
        self.assertEqual(run("stop", {"cwd": self.root}, self.root, driver=True)[1].strip(), "")
        write(os.path.join(self.work, "x.md"), "# no status\n")
        self.assertEqual(run("stop", {"cwd": self.root, "stop_hook_active": True}, self.root)[1].strip(), "")


if __name__ == "__main__":
    unittest.main()
