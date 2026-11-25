#!/usr/bin/env python3
"""Cases for the shared user-alerts module: writing an alert, claiming it once among concurrent agent-sessions,
and returning or deleting a claimed alert by what the walk-minutes record.

Every case points HOME at a scratch directory, so the user's own alerts and walk-minutes are never touched.
Prints one line per case and exits non-zero if any case fails.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_FILE = (Path(__file__).resolve().parents[1]
               / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")
_specification = importlib.util.spec_from_file_location(
    "user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common", MODULE_FILE)
alerts = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(alerts)

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
DEFAULT_SEAT = alerts.USER_ALERT_AGENT_SEAT_WHEN_ALERT_NAMES_NONE
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def fresh_home(root, name):
    home = root / name
    home.mkdir()
    os.environ["HOME"] = str(home)
    return home / ".local/state/nedsnodes/user-alerts"


class RenameRacedByAnotherAgentSession:
    """os, except that each rename first finds its source gone, as when another agent-session moved it."""

    def __getattr__(self, name):
        return getattr(os, name)

    @staticmethod
    def rename(source, target):
        raise FileNotFoundError(2, "No such file or directory", str(source))


class FirstRenameRacedByAnotherAgentSession:
    """os, except that the first rename finds its source gone; later renames happen, so a case can check that
    the files after a raced one are still handled."""

    def __init__(self):
        self.raced = False

    def __getattr__(self, name):
        return getattr(os, name)

    def rename(self, source, target):
        if not self.raced:
            self.raced = True
            raise FileNotFoundError(2, "No such file or directory", str(source))
        return os.rename(source, target)


def claimed_at(directory, alert_id, moment):
    path = directory / "claimed" / f"{alert_id}.json"
    os.utime(path, (moment.timestamp(), moment.timestamp()))
    return path


def run_write_cases(root):
    directory = fresh_home(root, "write")
    alert_id = alerts.user_alert_write_to_pending("merge-lane-2 is down", "notice\n  ssh x", "restart it", now=NOW)
    written = directory / "pending" / f"{alert_id}.json"
    alert = json.loads(written.read_text(encoding="utf-8")) if written.is_file() else {}
    check("an alert is written into pending/ with its id, time, title, notice text and action, naming no agent-seat",
          alert == {"id": alert_id, "written_at": "2026-10-27T12:00:00+00:00", "title": "merge-lane-2 is down",
                    "alert_text": "notice\n  ssh x", "action": "restart it", "claiming_agent_seat_name": None}, repr(alert))
    check("the alert's id starts with the UTC time it was written",
          alert_id.startswith("20261027T120000Z-"), alert_id)
    check("nothing is left in being-written/, where the file was written before its rename",
          list((directory / "being-written").iterdir()) == [], repr(list((directory / "being-written").iterdir())))


def agent_home(name):
    (Path(os.environ["HOME"]) / "agents" / name / ".git").mkdir(parents=True)


def run_agent_seat_cases(root):
    directory = fresh_home(root, "agent-seat")
    agent_home("seat-x")
    agent_home("seat-y")
    agent_home(DEFAULT_SEAT)
    for_x = alerts.user_alert_write_to_pending("for x", "text", "act", now=NOW - timedelta(hours=2), claiming_agent_seat_name="seat-x")
    for_none = alerts.user_alert_write_to_pending("for none", "text", "act", now=NOW - timedelta(hours=1))
    written = json.loads((directory / "pending" / f"{for_x}.json").read_text(encoding="utf-8"))
    check("an alert written for an agent-seat names it", written.get("claiming_agent_seat_name") == "seat-x", repr(written))
    by_y = alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed("seat-y", now=NOW)
    check("an agent-session of another agent-seat claims neither an alert for seat-x nor one naming none",
          by_y == [] and sorted(path.stem for path in (directory / "pending").iterdir()) == [for_x, for_none],
          repr(by_y))
    by_unknown = alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(None, now=NOW)
    check("an agent-session whose agent-seat is unknown claims nothing", by_unknown == [], repr(by_unknown))
    by_x = alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed("seat-x", now=NOW)
    check("seat-x's agent-session claims the alert for seat-x and not the one naming none",
          [alert["id"] for alert in by_x] == [for_x]
          and [path.stem for path in (directory / "pending").iterdir()] == [for_none], repr(by_x))
    by_default = alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=NOW)
    check(f"{DEFAULT_SEAT}'s agent-session claims the alert naming none",
          [alert["id"] for alert in by_default] == [for_none], repr(by_default))

    claimed_at(directory, for_x, NOW - timedelta(minutes=31))
    claimed_at(directory, for_none, NOW - timedelta(minutes=31))
    alerts.user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes(now=NOW)
    by_default = alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=NOW)
    by_x = alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed("seat-x", now=NOW)
    check("an alert returned to pending/ after 30 minutes keeps its agent-seat: only that agent-seat claims it again",
          [alert["id"] for alert in by_default] == [for_none] and [alert["id"] for alert in by_x] == [for_x]
          and by_x[0].get("claiming_agent_seat_name") == "seat-x", repr((by_default, by_x)))

    directory = fresh_home(root, "agent-seat-name-opening-with-underscore")
    agent_home("_seat-u")
    raised = None
    try:
        alerts.user_alert_write_to_pending("for u", "text", "act", now=NOW, claiming_agent_seat_name="_seat-u")
    except ValueError as error:
        raised = error
    check("an alert is written for an agent-seat whose name opens with _, which scripts/launch-claude-ubuntu accepts",
          raised is None and len(list((directory / "pending").glob("*.json"))) == 1, repr(raised))

    for name, agent_seat in (("no-agent-home", "seat-z"), ("not-a-checkout", "seat-z-worktrees"),
                             ("path-outside-agents", "../seat-x")):
        directory = fresh_home(root, f"refused-{name}")
        (Path(os.environ["HOME"]) / "agents" / "seat-z-worktrees").mkdir(parents=True)
        agent_home("seat-x")
        raised = None
        try:
            alerts.user_alert_write_to_pending("for z", "text", "act", now=NOW, claiming_agent_seat_name=agent_seat)
        except ValueError as error:
            raised = error
        check(f"writing an alert for an agent-seat with no agent-home ({name}) raises ValueError and writes no file",
              raised is not None and "no user-alert was written" in str(raised)
              and not any(path.is_file() for path in directory.rglob("*")), repr(raised))


def run_unreadable_pending_cases(root):
    directory = fresh_home(root, "unreadable-pending")
    (directory / "pending").mkdir(parents=True)
    (directory / "pending" / "0-not-an-object.json").write_text("[not an object]", encoding="utf-8")
    after = alerts.user_alert_write_to_pending("after", "text", "act", now=NOW)
    raised = None
    try:
        alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed("seat-y", now=NOW)
    except ValueError as error:
        raised = error
    check("a pending file that is not a JSON object raises ValueError naming unreadable/, even in an agent-seat it "
          "would not go to, and is moved into unreadable/", raised is not None and ".local/state/nedsnodes/user-alerts/unreadable/" in str(raised)
          and (directory / "unreadable" / "0-not-an-object.json").is_file(), repr(raised))
    claimed = alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=NOW)
    check("after a pending file that is not a JSON object, the next claim takes the alerts sorted after it",
          [alert["id"] for alert in claimed] == [after], repr(claimed))

    directory = fresh_home(root, "unreadable-pending-directory")
    (directory / "pending" / "0-a-directory.json").mkdir(parents=True)
    after = alerts.user_alert_write_to_pending("after", "text", "act", now=NOW)
    raised = None
    try:
        alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed("seat-y", now=NOW)
    except IsADirectoryError as error:
        raised = error
    check("a pending entry that cannot be read, a directory, raises its OSError naming unreadable/ and is moved there",
          raised is not None and ".local/state/nedsnodes/user-alerts/unreadable/" in str(raised)
          and (directory / "unreadable" / "0-a-directory.json").is_dir()
          and not (directory / "pending" / "0-a-directory.json").exists(), repr(raised))
    later = NOW + timedelta(minutes=31)
    alerts.user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes(
        now=later)
    claimed = alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=later)
    check("after a pending entry that cannot be read, a release then a claim 31 minutes later takes the alerts "
          "sorted after it, and the entry stays in unreadable/",
          [alert["id"] for alert in claimed] == [after]
          and (directory / "unreadable" / "0-a-directory.json").is_dir(), repr(claimed))


class UtimeFindsNothing:
    """os, except that setting a modification time finds no file, as for a dangling link moved into claimed/."""

    def __getattr__(self, name):
        return getattr(os, name)

    @staticmethod
    def utime(path, times):
        raise FileNotFoundError(2, "No such file or directory", str(path))


def run_unreadable_pending_dangling_link_case(root):
    directory = fresh_home(root, "unreadable-pending-dangling-link")
    (directory / "pending" / "a-directory").mkdir(parents=True)
    # Resolves from pending/ only, so once moved it dangles.
    (directory / "pending" / "0-dangling.json").symlink_to("a-directory")
    real_os, alerts.os = alerts.os, UtimeFindsNothing()
    raised = None
    try:
        alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=NOW)
    except OSError as error:
        raised = error
    finally:
        alerts.os = real_os
    unreadable_entry = directory / "unreadable" / "0-dangling.json"
    check("a pending link to a directory that dangles once moved is reported, not read as another agent-session's "
          "claim, even when setting a modification time would find nothing, and is moved into unreadable/",
          isinstance(raised, IsADirectoryError) and ".local/state/nedsnodes/user-alerts/unreadable/" in str(raised) and unreadable_entry.is_symlink()
          and not (directory / "claimed" / "0-dangling.json").is_symlink(), repr(raised))


def run_claim_cases(root):
    directory = fresh_home(root, "claim")
    check("with no pending/ directory, nothing is claimed", alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=NOW) == [])
    first = alerts.user_alert_write_to_pending("one", "text", "act", now=NOW - timedelta(hours=2))
    second = alerts.user_alert_write_to_pending("two", "text", "act", now=NOW - timedelta(hours=1))
    claimed = alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=NOW)
    check("a claim returns every pending alert, oldest first",
          [alert["id"] for alert in claimed] == [first, second], repr(claimed))
    check("a claim moves each alert from pending/ into claimed/",
          list((directory / "pending").iterdir()) == []
          and sorted(path.stem for path in (directory / "claimed").iterdir()) == [first, second])
    mtime = (directory / "claimed" / f"{first}.json").stat().st_mtime
    check("a claimed alert's modification time is the claim time, not the time it was written",
          mtime == NOW.timestamp(), repr(mtime))
    check("a second claim finds nothing left to claim", alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=NOW) == [])

    directory = fresh_home(root, "claim-raced")
    alerts.user_alert_write_to_pending("one", "text", "act", now=NOW)
    real_os = alerts.os
    alerts.os = RenameRacedByAnotherAgentSession()
    try:
        raised, claimed = None, None
        try:
            claimed = alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=NOW)
        except Exception as error:  # noqa: BLE001 - the case checks that nothing escapes
            raised = error
    finally:
        alerts.os = real_os
    check("an alert another agent-session claimed first is skipped, not an error",
          raised is None and claimed == [], repr((raised, claimed)))

    fresh_home(root, "claim-first-raced")
    alerts.user_alert_write_to_pending("one", "text", "act", now=NOW - timedelta(hours=1))
    second = alerts.user_alert_write_to_pending("two", "text", "act", now=NOW)
    alerts.os = FirstRenameRacedByAnotherAgentSession()
    try:
        claimed = alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=NOW)
    finally:
        alerts.os = real_os
    check("after an alert another agent-session claimed first, the alerts after it are still claimed",
          [alert["id"] for alert in claimed] == [second], repr(claimed))


CONCURRENT_CLAIMER = """
import importlib.util, json, sys, time
from pathlib import Path
specification = importlib.util.spec_from_file_location("alerts", sys.argv[1])
alerts = importlib.util.module_from_spec(specification)
specification.loader.exec_module(alerts)
while not Path(sys.argv[2]).exists():
    time.sleep(0.001)
print(json.dumps([alert["id"] for alert in alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(alerts.USER_ALERT_AGENT_SEAT_WHEN_ALERT_NAMES_NONE)]))
"""


def run_concurrent_claim_cases(root):
    directory = fresh_home(root, "concurrent")
    alert_ids = [alerts.user_alert_write_to_pending(f"alert {n}", "text", "act") for n in range(20)]
    start = root / "concurrent-start"
    claimers = [subprocess.Popen([sys.executable, "-c", CONCURRENT_CLAIMER, str(MODULE_FILE), str(start)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=dict(os.environ))
                for _ in range(2)]
    start.touch()
    results = [claimer.communicate(timeout=60) for claimer in claimers]
    claimed = [alert_id for output, _ in results for alert_id in json.loads(output or "[]")]
    check("two agent-sessions claiming at once: each alert is claimed by exactly one, and neither fails",
          sorted(claimed) == sorted(alert_ids) and all(claimer.returncode == 0 for claimer in claimers)
          and all(error == "" for _, error in results), repr(results))
    check("after two concurrent claims every alert is in claimed/ once, and none in pending/",
          sorted(path.stem for path in (directory / "claimed").iterdir()) == sorted(alert_ids)
          and list((directory / "pending").iterdir()) == [])


def run_release_cases(root):
    directory = fresh_home(root, "release")
    home = Path(os.environ["HOME"])
    unrecorded = alerts.user_alert_write_to_pending("unrecorded", "text", "act")
    in_open_walk = alerts.user_alert_write_to_pending("open walk", "text", "act")
    in_closed_walk = alerts.user_alert_write_to_pending("closed walk", "text", "act")
    fresh = alerts.user_alert_write_to_pending("fresh", "text", "act")
    alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=NOW)
    for alert_id in (unrecorded, in_open_walk, in_closed_walk):
        claimed_at(directory, alert_id, NOW - timedelta(minutes=31))
    claimed_at(directory, fresh, NOW - timedelta(minutes=29))
    open_walk = home / "agents/merge-lane-2/docs/walk"
    open_walk.mkdir(parents=True)
    (open_walk / "a-walk-minutes.md").write_text(f"- Re-planned.\n#user_alert {in_open_walk}\n", encoding="utf-8")
    closed_walk = home / "nedsnodes-logs/walk"
    closed_walk.mkdir(parents=True)
    (closed_walk / "b-walk-minutes.md").write_text(f"#user_alert {in_closed_walk}\n", encoding="utf-8")
    (closed_walk / "b-walk.md").write_text(f"#user_alert {unrecorded}\n", encoding="utf-8")
    alerts.user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes(now=NOW)
    pending = sorted(path.stem for path in (directory / "pending").iterdir())
    claimed = sorted(path.stem for path in (directory / "claimed").iterdir())
    check("a claimed alert no walk-minutes name returns to pending/ after 30 minutes; a walk-document naming it "
          "does not count", pending == [unrecorded], repr(pending))
    check("claimed alerts that open or closed walk-minutes name are deleted, and one claimed under 30 minutes "
          "ago stays", claimed == [fresh], repr(claimed))

    directory = fresh_home(root, "release-raced")
    alert_id = alerts.user_alert_write_to_pending("raced", "text", "act")
    alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=NOW)
    claimed_at(directory, alert_id, NOW - timedelta(hours=1))
    real_os = alerts.os
    alerts.os = RenameRacedByAnotherAgentSession()
    try:
        raised = None
        try:
            alerts.user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes(now=NOW)
        except Exception as error:  # noqa: BLE001 - the case checks that nothing escapes
            raised = error
    finally:
        alerts.os = real_os
    check("a claimed alert another agent-session returned first is skipped, not an error",
          raised is None, repr(raised))

    directory = fresh_home(root, "release-first-raced")
    first = alerts.user_alert_write_to_pending("one", "text", "act", now=NOW - timedelta(hours=2))
    second = alerts.user_alert_write_to_pending("two", "text", "act", now=NOW - timedelta(hours=1))
    alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=NOW)
    for alert_id in (first, second):
        claimed_at(directory, alert_id, NOW - timedelta(hours=1))
    alerts.os = FirstRenameRacedByAnotherAgentSession()
    try:
        alerts.user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes(now=NOW)
    finally:
        alerts.os = real_os
    pending = sorted(path.stem for path in (directory / "pending").iterdir())
    check("after a claimed alert another agent-session returned first, the alerts after it are still returned",
          pending == [second], repr(pending))

    directory = fresh_home(root, "release-vanished-while-listed")
    alert_id = alerts.user_alert_write_to_pending("old", "text", "act")
    alerts.user_alerts_claim_every_pending_for_agent_seat_by_rename_into_claimed(DEFAULT_SEAT, now=NOW)
    claimed_at(directory, alert_id, NOW - timedelta(hours=1))
    # A dangling link sorts first and fails stat() with FileNotFoundError, as a file moved away after listing.
    (directory / "claimed" / "0-moved-away.json").symlink_to(directory / "nowhere.json")
    raised = None
    try:
        alerts.user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes(now=NOW)
    except Exception as error:  # noqa: BLE001 - the case checks that nothing escapes
        raised = error
    pending = sorted(path.stem for path in (directory / "pending").iterdir())
    check("a claimed alert moved away between listing and reading is skipped, and the alerts after it are "
          "still returned", raised is None and pending == [alert_id], repr((raised, pending)))

    home = Path(fresh_home(root, "minutes-vanished")).parents[3]
    minutes = home / "nedsnodes-logs/walk"
    minutes.mkdir(parents=True)
    (minutes / "b-walk-minutes.md").write_text("#user_alert recorded-id\n", encoding="utf-8")
    real_walk_minutes_files = alerts.walk_minutes_files
    alerts.walk_minutes_files = lambda home: [minutes / "a-removed-walk-minutes.md", minutes / "b-walk-minutes.md"]
    raised, ids = None, None
    try:
        ids = alerts.user_alert_ids_named_in_walk_minutes(home)
    except Exception as error:  # noqa: BLE001 - the case checks that nothing escapes
        raised = error
    finally:
        alerts.walk_minutes_files = real_walk_minutes_files
    check("walk-minutes removed while they are read are skipped, and the walk-minutes after them still read",
          raised is None and ids == {"recorded-id"}, repr((raised, ids)))

    fresh_home(root, "release-empty")
    check("with no claimed/ directory, releasing does nothing",
          alerts.user_alerts_claimed_delete_if_recorded_in_approval_walk_minutes_else_release_to_pending_after_30_minutes(now=NOW) is None)


with tempfile.TemporaryDirectory() as temporary_directory:
    scratch = Path(temporary_directory)
    run_write_cases(scratch)
    run_agent_seat_cases(scratch)
    run_unreadable_pending_cases(scratch)
    run_unreadable_pending_dangling_link_case(scratch)
    run_claim_cases(scratch)
    run_concurrent_claim_cases(scratch)
    run_release_cases(scratch)

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
