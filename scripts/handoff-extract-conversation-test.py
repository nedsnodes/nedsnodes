#!/usr/bin/env python3
"""Tests for handoff-extract-conversation.py.

Run: python3 scripts/handoff-extract-conversation-test.py
Prints one line per case and exits non-zero if any case fails.

Every case builds its own transcript in a temporary directory, so the tests
never read a real session and never touch ~/.claude.
"""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("handoff-extract-conversation.py")

_spec = importlib.util.spec_from_file_location("handoff_extract_conversation", SCRIPT_PATH)
extractor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extractor)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def user_record(text, **overrides):
    record = {"type": "user", "message": {"content": text}}
    record.update(overrides)
    return record


def assistant_record(text, **overrides):
    record = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }
    record.update(overrides)
    return record


def write_transcript(directory, name, records, trailing_raw_lines=()):
    transcript_path = Path(directory) / name
    with transcript_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
        for raw in trailing_raw_lines:
            handle.write(raw)
    return transcript_path


def ordinary_records():
    return [
        user_record("first prompt"),
        assistant_record("first answer"),
        user_record("the boundary prompt\nwith a second line"),
        assistant_record("answer after the boundary"),
        user_record("last prompt"),
        assistant_record("last answer"),
    ]


with tempfile.TemporaryDirectory() as workspace:
    # --- Dialog selection -------------------------------------------------
    path = write_transcript(workspace, "plain.jsonl", ordinary_records())
    turns, skips = extractor.read_dialog_turns(path)
    check("reads every dialog turn", len(turns) == 6, f"got {len(turns)}")
    check("no skips on a clean transcript", not any(skips.values()), str(skips))

    # minimum_words=0 isolates boundary selection from the word floor.
    selected, start, quoted = extractor.select_turns_from_boundary(turns, "the boundary prompt", 0)
    check("boundary starts at the quoted prompt", selected[0]["text"].startswith("the boundary prompt"))
    check("boundary carries to the end", len(selected) == 4, f"got {len(selected)}")
    check("boundary reports its index", start == 2 and quoted == 2, f"got {start},{quoted}")

    try:
        extractor.select_turns_from_boundary(turns, "a prompt nobody typed")
        check("missing boundary refuses", False, "no exception raised")
    except extractor.TranscriptProblem:
        check("missing boundary refuses", True)

    # --- The word floor widens a too-tight boundary ------------------------
    # Ten topics of ~600 words each: comfortably above a 2500-word floor in
    # total, comfortably below it for any single topic.
    wordy = []
    for topic in range(10):
        wordy.append(user_record(f"topic {topic} opens"))
        wordy.append(assistant_record(" ".join(["word"] * 600)))
    path = write_transcript(workspace, "wordy.jsonl", wordy)
    turns, _ = extractor.read_dialog_turns(path)

    selected, start, quoted = extractor.select_turns_from_boundary(turns, "topic 9 opens", 2500)
    check("floor widens a too-tight boundary", start < quoted, f"start {start}, quoted {quoted}")
    check("widened selection clears the floor", extractor.word_count(selected) >= 2500,
          extractor.word_count(selected))
    check("widened boundary lands on a user prompt", selected[0]["voice"] == "user", selected[0]["voice"])

    selected, start, quoted = extractor.select_turns_from_boundary(turns, "topic 1 opens", 2500)
    check("a boundary already clearing the floor is untouched", start == quoted, f"{start} vs {quoted}")

    # Quoting the LAST topic forces the widening walk to traverse the whole
    # session (a boundary already at index 0 would pass this trivially).
    selected, start, _ = extractor.select_turns_from_boundary(turns, "topic 9 opens", 999999)
    check("an unreachable floor carries the whole session", start == 0, f"got {start}")

    # --- The default: a floor-sized tail, no boundary named ---------------
    selected, start = extractor.select_tail_clearing_floor(turns, 2500)
    check("default tail clears the floor", extractor.word_count(selected) >= 2500,
          extractor.word_count(selected))
    check("default tail opens on a user prompt", selected[0]["voice"] == "user", selected[0]["voice"])
    check("default tail leaves earlier turns behind", start > 0, f"got {start}")
    check(
        "default tail carries no more than it needs",
        extractor.word_count(selected) < 2500 + 1300,
        extractor.word_count(selected),
    )

    selected, start = extractor.select_tail_clearing_floor(turns, 999999)
    check("an unreachable floor carries everything", start == 0 and len(selected) == len(turns))

    exit_code = extractor.main(["--transcript-path", str(path), "--output", str(Path(workspace) / "default.md")])
    check("extraction runs with no boundary argument at all", exit_code == 0, f"got {exit_code}")
    default_text = (Path(workspace) / "default.md").read_text(encoding="utf-8")
    check("default extraction names the floor in its header",
          f"clearing {extractor.MINIMUM_DIALOG_WORDS} words" in default_text,
          default_text[:200])

    # --- Noise classes are dropped ---------------------------------------
    noisy = [
        user_record("kept prompt"),
        {"type": "user", "isMeta": True,
         "message": {"content": "<local-command-caveat>injected</local-command-caveat>"}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "huge tool dump"}]}},
        {
            "type": "assistant",
            "message": {"content": [{"type": "thinking", "thinking": "private reasoning"},
                                     {"type": "tool_use", "name": "Bash", "input": {}},
                                     {"type": "text", "text": "kept answer"}]},
        },
        user_record("subagent prompt", isSidechain=True),
        assistant_record("subagent answer", isSidechain=True),
        {"type": "system", "content": "system notice"},
        {"type": "queue-operation", "operation": "enqueue", "content": "<task-notification/>"},
        {"type": "file-history-snapshot", "snapshot": {}},
    ]
    path = write_transcript(workspace, "noisy.jsonl", noisy)
    turns, _ = extractor.read_dialog_turns(path)
    kept = [turn["text"] for turn in turns]
    check("keeps both voices, drops all noise", kept == ["kept prompt", "kept answer"], str(kept))

    # --- Messages typed while the agent was mid-turn -----------------------
    # These are NOT user records. The harness queues them and persists an
    # attachment of type queued_command, which the type filter dropped — so
    # every message the user typed during a running turn was invisible to the
    # handoff. Shapes below are copied from the field (2026-08-23 census of 530
    # transcripts: 294 human-origin records, 283 appearing nowhere else in
    # their own transcript), not from the design.
    def queued(prompt, kind="human"):
        origin = {"kind": kind} if kind is not None else None
        return {"type": "attachment",
                "attachment": {"type": "queued_command", "prompt": prompt, "origin": origin}}

    mid_turn = [
        user_record("first prompt"),
        assistant_record("working on it"),
        queued("the post tool hook is the magic"),
        assistant_record("answer after the interruption"),
    ]
    path = write_transcript(workspace, "mid-turn.jsonl", mid_turn)
    turns, _ = extractor.read_dialog_turns(path)
    kept = [(turn["voice"], turn["text"]) for turn in turns]
    check(
        "a message typed mid-turn is carried, in the position it was delivered",
        kept == [("user", "first prompt"), ("assistant", "working on it"),
                 ("user", "the post tool hook is the magic"),
                 ("assistant", "answer after the interruption")],
        str(kept),
    )

    other_origins = [
        user_record("real prompt"),
        queued("<cross-session-message from-name=\"merge-lane\">merge #143</cross-session-message>", kind="peer"),
        queued("<task-notification><task-id>b1</task-id></task-notification>", kind=None),
        queued("", kind="human"),
        {"type": "attachment", "attachment": {"type": "total_tokens_reminder", "text": "<total_tokens>1</total_tokens>"}},
        assistant_record("real answer"),
    ]
    path = write_transcript(workspace, "other-origins.jsonl", other_origins)
    turns, _ = extractor.read_dialog_turns(path)
    kept = [turn["text"] for turn in turns]
    check(
        "another agent's message, a task notification, an empty one and a "
        "non-command attachment all stay out",
        kept == ["real prompt", "real answer"],
        str(kept),
    )

    # A message typed mid-turn and then interrupted is persisted twice: the
    # queued_command attachment, and a plain user record when the harness
    # re-sends it after the interrupt (field specimen 2026-08-12: four records
    # and 5.7 seconds apart). The extract carries it once, and the short
    # answer that follows is the reply to it, not an acknowledgement of the
    # interrupt.
    resent_after_interrupt = [
        user_record("first prompt"),
        assistant_record("working on it"),
        queued("stop. I think another session is duplicating your work."),
        {"type": "user", "message": {"content": [{"type": "text", "text": "[Request interrupted by user]"}]}},
        {"type": "queue-operation", "operation": "dequeue"},
        user_record("stop. I think another session is duplicating your work."),
        assistant_record("Stopping."),
    ]
    path = write_transcript(workspace, "resent-after-interrupt.jsonl", resent_after_interrupt)
    turns, skips = extractor.read_dialog_turns(path)
    kept = [(turn["voice"], turn["text"]) for turn in turns]
    check(
        "a mid-turn message the harness re-sends after an interrupt is carried "
        "once, and the short answer after it survives",
        kept == [("user", "first prompt"), ("assistant", "working on it"),
                 ("user", "stop. I think another session is duplicating your work."),
                 ("assistant", "Stopping.")]
        and skips["resent_after_interrupt"] == 1,
        f"{kept} skips={skips}",
    )

    # Scope guard (passes with or without the de-duplication): the same short
    # answer twice with NO interrupt between is two replies — field shape
    # 2026-08-24, "y" approving item 1 of a walk, then "y" approving item 2,
    # 25 records and 121 seconds apart.
    two_approvals = [
        user_record("walk me through the items"),
        assistant_record("Item 1: rename the flag. Approve?"),
        queued("y"),
        assistant_record("Item 1 is in and pushed. Item 2: drop the alias. Approve?"),
        user_record("y"),
        assistant_record("Item 2 is in."),
    ]
    path = write_transcript(workspace, "two-approvals.jsonl", two_approvals)
    turns, _ = extractor.read_dialog_turns(path)
    kept = [turn["text"] for turn in turns]
    check(
        "the same short answer twice with no interrupt between is two replies, both carried",
        kept == ["walk me through the items", "Item 1: rename the flag. Approve?", "y",
                 "Item 1 is in and pushed. Item 2: drop the alias. Approve?", "y", "Item 2 is in."],
        str(kept),
    )

    # --- Harness-injected pseudo-prompts and their acknowledgements --------
    # Fixture shapes are copied from the field, not the design: a delivered
    # monitor notification persists as a PLAIN user record — no isMeta, string
    # content — indistinguishable by type from a typed prompt. The original
    # fixture modeled it as a queue-operation record, which the filter always
    # dropped, so the tests stayed green while real extracts ran 79% noise
    # (2026-08-17 census of 341 transcripts).
    notification_text = (
        "<task-notification>\n<task-id>b123</task-id>\n"
        '<summary>Monitor event: "fleet watcher"</summary>\n'
        "<event>some seat said something</event>\n"
        "If this event is something the user would act on now, send a "
        "PushNotification. Routine or benign output doesn't need one.\n"
        "</task-notification>"
    )
    injected = [
        user_record("real question"),
        assistant_record("real answer to the question"),
        user_record(notification_text),
        assistant_record("Routine — noted. On watch."),
        user_record(notification_text),
        assistant_record(" ".join(["urgent"] * 80)),
        user_record("<command-message>walk-me-through</command-message> "
                    "<command-name>/walk-me-through</command-name>"),
        user_record("<local-command-stdout>Set model to Opus</local-command-stdout>"),
        user_record("[Request interrupted by user]"),
        user_record("<bash-input>git status</bash-input>"),
        assistant_record("short reply after a real prompt"),
    ]
    path = write_transcript(workspace, "injected.jsonl", injected)
    turns, skips = extractor.read_dialog_turns(path)
    kept = [turn["text"] for turn in turns]
    check("notification pseudo-prompts are dropped",
          not any("<task-notification>" in text for text in kept), str(kept)[:200])
    check("command and interrupt records are dropped",
          not any(text.startswith(("<command-", "<local-command", "[Request interrupted"))
                  for text in kept), str(kept)[:200])
    check("the short acknowledgement falls with its notification",
          "Routine — noted. On watch." not in kept, str(kept)[:200])
    check("a long reaction to a notification survives as dialog",
          any(text.startswith("urgent") for text in kept), str(kept)[:200])
    check("bash-input is kept — the user typed it",
          "<bash-input>git status</bash-input>" in kept, str(kept)[:200])
    check("a short answer after a real prompt is kept",
          "short reply after a real prompt" in kept, str(kept)[:200])
    check("injected records are counted", skips["injected"] == 5, str(skips))
    check("acknowledgements are counted", skips["acknowledgement"] == 1, str(skips))

    # --- Slash commands typed with words ----------------------------------
    # The record shapes are copied from real transcripts: a skill command
    # (merge-lane, 2026-09-01T03:16:53Z — queued while the agent worked, then
    # delivered as a tagged user record followed by the skill's isMeta body),
    # a built-in command (opens with <command-name>, indented, answered by
    # local-command-stdout), and commands with no words. Before the fix every
    # one of them was dropped as injected, words included.
    typed_words = "what is standing with me. or any other qeustions"
    slash = [
        {"type": "queue-operation", "operation": "enqueue",
         "content": f"/walk-me-through {typed_words}"},
        user_record("<command-message>walk-me-through</command-message>\n"
                    "<command-name>/walk-me-through</command-name>\n"
                    f"<command-args>{typed_words}</command-args>",
                    origin={"kind": "human"}),
        user_record([{"type": "text", "text": "Base directory for this skill: "
                      "/x/.claude/skills/walk-me-through\n\n# Walk me through"}],
                    isMeta=True),
        assistant_record("Item 1 of 3: the first thing standing with you"),
        user_record("<command-name>/model</command-name>\n"
                    "            <command-message>model</command-message>\n"
                    "            <command-args>opus</command-args>"),
        user_record("<local-command-stdout>Set model to opus</local-command-stdout>"),
        user_record("<command-message>handoff</command-message>\n"
                    "<command-name>/handoff</command-name>",
                    origin={"kind": "human"}),
        user_record("<command-name>/compact</command-name>\n"
                    "            <command-message>compact</command-message>\n"
                    "            <command-args></command-args>"),
        user_record("<command-message>walk-me-through</command-message>\n"
                    "<command-name>/walk-me-through</command-name>\n"
                    "<command-args>these - 1 did you measure</command-args>"),
        user_record("<command-message>walk-me-through</command-message>\n"
                    "<command-name>/walk-me-through</command-name>\n"
                    "<command-args>sent by another seat</command-args>",
                    origin={"kind": "peer"}),
        {"type": "attachment", "attachment": {
            "type": "queued_command", "origin": {"kind": "human"},
            "prompt": "Still confused. /walk-me-through item 3"}},
        assistant_record("Item 3, retold as one story"),
    ]
    path = write_transcript(workspace, "slash.jsonl", slash)
    turns, skips = extractor.read_dialog_turns(path)
    kept = [turn["text"] for turn in turns]
    users = [turn["text"] for turn in turns if turn["voice"] == "user"]
    check("a skill command's words are carried as one user turn",
          users.count(f"/walk-me-through {typed_words}") == 1, str(users))
    check("a built-in command's words are carried",
          "/model opus" in users, str(users))
    check("a command recorded before origin existed is carried",
          "/walk-me-through these - 1 did you measure" in users, str(users))
    check("the skill's expanded body stays out",
          not any("Base directory for this skill" in text for text in kept), str(kept)[:200])
    check("a command with no words stays out",
          not any(text.startswith(("/handoff", "/compact", "<command-")) for text in kept),
          str(kept))
    check("a command of non-human origin stays out",
          not any("sent by another seat" in text for text in kept), str(kept))
    check("a slash command inside a queued message is carried once",
          users.count("Still confused. /walk-me-through item 3") == 1, str(users))
    check("the queued copy of a command is not carried a second time",
          sum(typed_words in text for text in kept) == 1, str(kept))
    check("the answer to a carried command survives",
          "Item 1 of 3: the first thing standing with you" in kept, str(kept))
    check("bare, non-human and stdout records are counted as injected",
          skips["injected"] == 4, str(skips))

    # A tool-bearing record between a notification and the next assistant text
    # means the agent did real work — its short conclusion is a report the
    # successor needs, not the notification's ack (review finding: it was
    # being dropped unrecoverably). Pure harness records leave the pair intact.
    tool_use_record = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "true"}}]}}
    tool_result_record = {"type": "user", "message": {"content": [
        {"type": "tool_result", "content": "ran"}]}}
    interleaved = [
        user_record("fix the bug please"),
        user_record(notification_text),
        tool_use_record,
        tool_result_record,
        assistant_record("Fixed — the null check in parse() was inverted. Tests pass."),
        user_record(notification_text),
        {"type": "queue-operation", "operation": "enqueue"},
        {"type": "system", "content": "notice"},
        assistant_record("Routine — noted. On watch."),
    ]
    path = write_transcript(workspace, "interleaved.jsonl", interleaved)
    turns, skips = extractor.read_dialog_turns(path)
    kept = [turn["text"] for turn in turns]
    check("a short real conclusion after tool work survives",
          any(text.startswith("Fixed —") for text in kept), str(kept)[:200])
    check("harness records between the pair do not save the ack",
          "Routine — noted. On watch." not in kept, str(kept)[:200])

    # "message": null appears on some harness record types; both content
    # readers must survive it (review finding: this crashed extraction).
    null_message = [
        user_record("real prompt"),
        user_record(notification_text),
        {"type": "progress", "message": None},
        {"type": "user", "message": None},
        assistant_record("Routine ack after a null-message record."),
    ]
    path = write_transcript(workspace, "null-message.jsonl", null_message)
    turns, skips = extractor.read_dialog_turns(path)
    check("a null message field does not crash extraction",
          [t["text"] for t in turns] == ["real prompt"], str(turns)[:200])

    # --- Short trailing handoff fragments are trimmed ----------------------
    tail_fragment = [
        user_record("penultimate prompt"),
        assistant_record(" ".join(["substantive"] * 100)),
        user_record("handoff please"),
        assistant_record("Writing the successor's first-action prompt:"),
    ]
    path = write_transcript(workspace, "tail-fragment.jsonl", tail_fragment)
    turns, _ = extractor.read_dialog_turns(path)
    selected, start = extractor.select_tail_clearing_floor(turns, 10)
    check("short dangling handoff fragment is trimmed",
          selected[-1]["text"] == "handoff please",
          selected[-1]["text"][:60])

    # The malformed line gives the run a skip count to report.
    path = write_transcript(workspace, "tail-fragment-with-malformed-line.jsonl", tail_fragment,
                            trailing_raw_lines=['{"type": "user", "message": BROKEN}\n'])
    fragment_output = Path(workspace) / "fragment-out.md"
    fragment_stderr = io.StringIO()
    with contextlib.redirect_stderr(fragment_stderr):
        exit_code = extractor.main(["--transcript-path", str(path),
                                    "--minimum-words", "10",
                                    "--output", str(fragment_output)])
    fragment_text = fragment_output.read_text(encoding="utf-8")
    fragment_errors = fragment_stderr.getvalue()
    check("stderr reports the trimmed fragment count",
          "Trimmed from the end: 1 short agent turn(s)" in fragment_errors,
          fragment_errors[:400])
    check("stderr reports the records skipped while reading",
          "Records skipped while reading: 1 malformed." in fragment_errors,
          fragment_errors[:400])
    check("stderr says turn counts are dialog only",
          "Turn counts are dialog only" in fragment_errors,
          fragment_errors[:400])
    check("the tail's header holds none of the lines stderr carries",
          not any(part in fragment_text for part in
                  ("Trimmed from the end", "Records skipped while reading", "Turn counts are dialog only")),
          fragment_text[:400])
    check("the tail's header keeps its boundary and turn counts",
          "Boundary: " in fragment_text and "Turns carried: 3 of 4 (104 words)." in fragment_text.split("\n"),
          fragment_text[:400])

    # argparse refuses via SystemExit(2); catch it so the suite survives.
    try:
        exit_code = extractor.main(["--transcript-path", str(path), "--minimum-words", "0"])
    except SystemExit as refusal:
        exit_code = refusal.code
    check("a zero word floor refuses with exit 2 instead of crashing",
          exit_code == 2, f"got {exit_code}")

    solid_tail = [
        user_record("a prompt"),
        assistant_record(" ".join(["substantive"] * 100)),
    ]
    path = write_transcript(workspace, "solid-tail.jsonl", solid_tail)
    turns, _ = extractor.read_dialog_turns(path)
    selected, _ = extractor.select_tail_clearing_floor(turns, 10)
    check("a substantive final answer survives the trim",
          selected[-1]["text"].startswith("substantive"), selected[-1]["text"][:40])

    # --- Companion file: the complete filtered dialog ----------------------
    long_session = []
    for chapter in range(10):
        long_session.append(user_record(f"chapter {chapter} question"))
        long_session.append(assistant_record(" ".join([f"chapter{chapter}"] * 300)))
    path = write_transcript(workspace, "companion-source.jsonl", long_session)
    tail_output = Path(workspace) / "seat-dialog-0003.md"
    exit_code = extractor.main(["--transcript-path", str(path), "--output", str(tail_output)])
    companion_output = Path(workspace) / "seat-dialog-0003-complete.md"
    check("companion extraction exits 0", exit_code == 0, f"got {exit_code}")
    check("companion file is written when turns are left behind",
          companion_output.is_file())
    companion_text = companion_output.read_text(encoding="utf-8") if companion_output.is_file() else ""
    check("companion carries every dialog turn",
          companion_text.count("\n## User\n") + companion_text.count("\n## Agent\n") == 20,
          companion_text.count("\n## "))
    tail_text = tail_output.read_text(encoding="utf-8")
    check("extract points at the companion", str(companion_output) in tail_text)
    check("extract names thinking in the transcript pointer", "thinking" in tail_text)
    check("extract header counts only real turns", " of 20 (" in tail_text, tail_text[:300])

    whole_session = ordinary_records()[:-1] + [assistant_record(" ".join(["closing"] * 80))]
    path = write_transcript(workspace, "whole-session.jsonl", whole_session)
    whole_output = Path(workspace) / "whole-out.md"
    extractor.main(["--transcript-path", str(path), "--output", str(whole_output)])
    check("no companion when the whole dialog is carried",
          not (Path(workspace) / "whole-out-complete.md").exists())

    # --- Tolerance: malformed line skipped and counted --------------------
    path = write_transcript(
        workspace, "malformed.jsonl", ordinary_records(),
        trailing_raw_lines=['{"type": "user", "message": BROKEN}\n', json.dumps(user_record("after the break")) + "\n"],
    )
    turns, skips = extractor.read_dialog_turns(path)
    check("malformed line is skipped", skips["malformed"] == 1, str(skips))
    check("reading continues past a malformed line", turns[-1]["text"] == "after the break", turns[-1]["text"])

    # --- Tolerance: partial final record ----------------------------------
    path = write_transcript(
        workspace, "partial.jsonl", ordinary_records(),
        trailing_raw_lines=['{"type": "user", "message": {"content": "cut off mid-writ'],
    )
    turns, skips = extractor.read_dialog_turns(path)
    check("partial final record is counted separately", skips["partial_final_record"] == 1, str(skips))
    check("partial final record is not fatal", len(turns) == 6, f"got {len(turns)}")

    # --- Tolerance: oversized record bounded ------------------------------
    giant = user_record("x" * (extractor.MAXIMUM_RECORD_BYTES + 100))
    path = write_transcript(workspace, "oversized.jsonl", [giant, *ordinary_records()])
    turns, skips = extractor.read_dialog_turns(path)
    check("oversized record is skipped by size", skips["oversized"] == 1, str(skips))
    check("oversized record does not defeat extraction", len(turns) == 6, f"got {len(turns)}")

    # --- Refusals ---------------------------------------------------------
    path = write_transcript(workspace, "empty.jsonl", [])
    exit_code = extractor.main(["--transcript-path", str(path), "--last-turns", "3"])
    check("empty transcript refuses with exit 4", exit_code == 4, f"got {exit_code}")

    path = write_transcript(workspace, "garbage.jsonl", [], trailing_raw_lines=["not json at all\n", "still not\n"])
    exit_code = extractor.main(["--transcript-path", str(path), "--last-turns", "3"])
    check("unparseable transcript refuses with exit 4", exit_code == 4, f"got {exit_code}")

    exit_code = extractor.main(["--transcript-path", str(Path(workspace) / "absent.jsonl"), "--last-turns", "3"])
    check("absent transcript reports exit 3", exit_code == 3, f"got {exit_code}")

    # --- Recovery mode and rendering --------------------------------------
    path = write_transcript(workspace, "recovery.jsonl", ordinary_records())
    output_path = Path(workspace) / "extraction.md"
    exit_code = extractor.main(
        ["--transcript-path", str(path), "--last-turns", "3", "--output", str(output_path)]
    )
    rendered = output_path.read_text(encoding="utf-8")
    check("recovery mode exits 0", exit_code == 0, f"got {exit_code}")
    check("recovery mode carries exactly N turns", rendered.count("\n## ") == 3, rendered.count("\n## "))
    check("extraction points at the full transcript", str(path) in rendered)
    check("extraction labels both voices", "## User" in rendered and "## Agent" in rendered)

    # --- Cross-directory id lookup ----------------------------------------
    elsewhere_session_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    projects_root = Path(workspace) / "projects"
    (projects_root / "-Some-Other-Worktree").mkdir(parents=True)
    write_transcript(
        projects_root / "-Some-Other-Worktree", f"{elsewhere_session_id}.jsonl", ordinary_records()
    )
    original_root = extractor.PROJECTS_ROOT
    try:
        extractor.PROJECTS_ROOT = projects_root
        found = extractor.find_transcript_path(
            elsewhere_session_id, Path("/Users/someone/Projects/elsewhere")
        )
        check(
            "finds a transcript in another project directory",
            found.name == f"{elsewhere_session_id}.jsonl",
            str(found),
        )

        try:
            extractor.find_transcript_path("ffffffff-0000-0000-0000-000000000000", Path("/nowhere"))
            check("missing session reports a problem", False, "no exception raised")
        except extractor.TranscriptProblem:
            check("missing session reports a problem", True)
    finally:
        extractor.PROJECTS_ROOT = original_root

    check(
        "keyed lookup mangles the worktree path",
        extractor.project_directory_for_working_directory(Path("/Users/el/Projects/nedsnodes")).name
        == "-Users-el-Projects-nedsnodes",
        extractor.project_directory_for_working_directory(Path("/Users/el/Projects/nedsnodes")).name,
    )

# --- Repeated agent paragraphs in the log-store's session dialogs ----------
CLOSING = "Answer A to approve, D to disapprove, or Z to defer this item."
with tempfile.TemporaryDirectory() as workspace:
    repeats = write_transcript(workspace, "repeats.jsonl", [
        assistant_record(f"Item one.\n\n{CLOSING}", timestamp="2026-09-01T08:00:00Z"),
        user_record(CLOSING, timestamp="2026-09-01T08:01:00Z"),
        assistant_record(f"Item two.\n\n\n  {CLOSING}  \n\nItem one.", timestamp="2026-09-01T08:02:00Z"),
        assistant_record(f"{CLOSING}\n\n{CLOSING}", timestamp="2026-09-01T08:03:00Z"),
    ])
    session_dialog = extractor.render_companion(*extractor.complete_dialog_turns_and_report(repeats))
    repeated_line = "(repeated: Answer A to approve, D to disapprove, or …)"
    check("the session dialog keeps an agent paragraph's first copy whole and makes each later copy the one "
          "line naming its first eight words",
          session_dialog.count(CLOSING) == 2 and session_dialog.count(repeated_line) == 3
          and "(repeated: Item one. …)" in session_dialog, session_dialog)
    check("the user's turns are never shortened, even when they repeat an agent paragraph",
          f"## User\n\n{CLOSING}\n" in session_dialog, session_dialog)
    check("a repeat keeps the blank lines around it, and a paragraph whose outer whitespace differs counts as "
          "the same",
          f"Item two.\n\n\n{repeated_line}\n\n(repeated: Item one. …)" in session_dialog, session_dialog)
    lines, notes = extractor.complete_dialog_lines_with_turn_timestamps(repeats)
    check("the lines dated for the search are the session dialog's lines, each repeat dated by its own turn",
          [line for line, _ in lines] == session_dialog.split("\n")
          and [stamp for line, stamp in lines if line == repeated_line]
          == ["2026-09-01T08:02:00Z", "2026-09-01T08:03:00Z", "2026-09-01T08:03:00Z"] and not notes,
          lines)
    long_paragraph = " ".join(f"word{number}" for number in range(12))
    long_repeats = write_transcript(workspace, "long.jsonl", [assistant_record(long_paragraph),
                                                               assistant_record(long_paragraph)])
    check("a repeat names only the first eight words of its paragraph",
          "(repeated: word0 word1 word2 word3 word4 word5 word6 word7 …)"
          in extractor.render_companion(*extractor.complete_dialog_turns_and_report(long_repeats)))
    subagent_turns = [{"voice": extractor.SUBAGENT_VOICE, "kind": "report", "text": CLOSING},
                      {"voice": "assistant", "text": CLOSING},
                      {"voice": extractor.SUBAGENT_VOICE, "kind": "report", "text": CLOSING}]
    check("subagent turns are never shortened, and do not count as the agent having shown a paragraph",
          [turn["text"] for turn in extractor.turns_with_repeated_agent_paragraphs_shortened(subagent_turns)]
          == [CLOSING, CLOSING, CLOSING])
    output = Path(workspace) / "seat-dialog-0001.md"
    extractor.main(["--transcript-path", str(repeats), "--last-turns", "1", "--output", str(output)])
    companion = output.with_name("seat-dialog-0001-complete.md").read_text(encoding="utf-8")
    check("the handoff's own dialog files keep every repeat whole",
          "(repeated:" not in output.read_text(encoding="utf-8") + companion and companion.count(CLOSING) == 5,
          companion)

# --- Queued messages the agent never read -----------------------------------
# Claude Code's records, each copied from a real transcript with only its content replaced: these cases
# check the extractor against that captured format.
def enqueue_record(content):
    return {"type": "queue-operation", "operation": "enqueue", "timestamp": "2026-11-07T22:22:52.871Z",
            "sessionId": "279d6b08-3a6b-4aea-802e-01c238ad967d", "content": content}


def dequeue_record():
    return {"type": "queue-operation", "operation": "dequeue", "timestamp": "2026-11-05T22:25:39.719Z",
            "sessionId": "279d6b08-3a6b-4aea-802e-01c238ad967d"}


def remove_record(content, reason=None):
    record = {"type": "queue-operation", "operation": "remove", "timestamp": "2026-11-06T01:37:45.122Z",
              "sessionId": "279d6b08-3a6b-4aea-802e-01c238ad967d", "content": content}
    if reason:
        record["reason"] = reason
    return record


def pop_all_record(content):
    return {"type": "queue-operation", "operation": "popAll", "timestamp": "2026-09-18T19:20:59.215Z",
            "sessionId": "da317042-4df3-48ab-b0ae-10a8d71f4f0b", "content": content}


def absorbed_attachment_record(prompt):
    return {"parentUuid": "a2118a2d-1f4f-4c10-9cb2-85c8130dd3b5", "isSidechain": False, "type": "attachment",
            "attachment": {"type": "queued_command", "prompt": prompt, "origin": {"kind": "human"}}}


INTRODUCTION = extractor.CONVERSATION_TAIL_QUEUED_USER_MESSAGES_NEVER_READ_BY_AGENT_INTRODUCTION
with tempfile.TemporaryDirectory() as workspace:
    path = write_transcript(workspace, "unread.jsonl", [
        *ordinary_records(),
        enqueue_record("absorbed mid-turn"),
        remove_record("absorbed mid-turn", "absorbed_mid_turn"),
        absorbed_attachment_record("absorbed mid-turn"),
        enqueue_record("taken off the queue by the user"),
        remove_record("taken off the queue by the user"),
        enqueue_record("returned to the input box"),
        pop_all_record("returned to the input box"),
        enqueue_record("dequeued as a prompt"),
        dequeue_record(),
        user_record("dequeued as a prompt"),
        assistant_record("an answer to the dequeued prompt"),
        enqueue_record("/walk-me-through whatever I need"),
        user_record("<command-message>walk-me-through</command-message>\n<command-name>/walk-me-through"
                    "</command-name>\n<command-args>whatever I need</command-args>"),
        enqueue_record("A"),
        enqueue_record('<cross-session-message from="bridge:session_01">merge it</cross-session-message>'),
        enqueue_record("<task-notification>\n<task-id>b1</task-id>\n</task-notification>"),
        enqueue_record('<agent-message from="a1">\n[Subagent hand-back] done\n</agent-message>'),
        assistant_record("an agent turn that has not read the queue"),
        enqueue_record('<pasted_content id="28f2">\nwhat the user pasted\n</pasted_content>'),
        enqueue_record("and a second thought"),
    ], trailing_raw_lines=["not json at all\n"])
    check("a message queued and never read is recovered, in the order typed, without another sender's "
          "tagged text and with the user's paste",
          extractor.claude_code_session_transcript_queued_user_messages_never_read_by_agent(path)
          == ["A", '<pasted_content id="28f2">\nwhat the user pasted\n</pasted_content>', "and a second thought"],
          extractor.claude_code_session_transcript_queued_user_messages_never_read_by_agent(path))
    output = Path(workspace) / "seat-dialog-0002.md"
    exit_code = extractor.main(["--transcript-path", str(path), "--output", str(output)])
    tail = output.read_text(encoding="utf-8")
    check("each unread message stays where it was typed: A before the agent turn after it, the rest at the end",
          exit_code == 0 and f"## User\n\n{INTRODUCTION}\n\nA\n\n## Agent\n\nan agent turn that has not read the queue" in tail
          and tail.split("\n---\n")[1].rstrip().endswith(
              f"## User\n\n{INTRODUCTION}\n\n<pasted_content id=\"28f2\">\nwhat the user pasted\n"
              f"</pasted_content>\n\nand a second thought"), tail)

    path = write_transcript(workspace, "dequeue-takes-the-later.jsonl", [
        *ordinary_records(),
        enqueue_record("typed first, never read"),
        enqueue_record("typed second, read"),
        dequeue_record(),
        user_record("typed second, read"),
    ])
    check("a dequeue takes the message the next prompt shows, not the oldest",
          extractor.claude_code_session_transcript_queued_user_messages_never_read_by_agent(path) == ["typed first, never read"],
          extractor.claude_code_session_transcript_queued_user_messages_never_read_by_agent(path))

    path = write_transcript(workspace, "dequeue-shows-nothing.jsonl", [
        *ordinary_records(), enqueue_record("/logout"), enqueue_record("typed later"), dequeue_record(),
    ])
    check("a dequeue that no prompt shows takes the oldest message",
          extractor.claude_code_session_transcript_queued_user_messages_never_read_by_agent(path) == ["typed later"],
          extractor.claude_code_session_transcript_queued_user_messages_never_read_by_agent(path))

    never_read = extractor.claude_code_session_transcript_queued_user_messages_never_read_by_agent
    path = write_transcript(workspace, "same-text-twice-dequeue.jsonl", [
        *ordinary_records(), enqueue_record("A"), enqueue_record("A"), dequeue_record(), user_record("A"),
    ])
    check("a dequeue and the record delivering it remove one of two equal messages", never_read(path) == ["A"], never_read(path))

    path = write_transcript(workspace, "same-text-twice-absorbed.jsonl", [
        *ordinary_records(), enqueue_record("A"), enqueue_record("A"),
        remove_record("A", "absorbed_mid_turn"), absorbed_attachment_record("A"),
    ])
    check("an absorbed removal and its attachment remove one of two equal messages", never_read(path) == ["A"], never_read(path))

    peer = '<cross-session-message from="bridge:session_01">merge it</cross-session-message>'
    path = write_transcript(workspace, "peer-dequeued-first.jsonl", [
        *ordinary_records(), enqueue_record("older reply"), enqueue_record(peer), dequeue_record(),
        user_record(f"Another Claude session sent a message:\n{peer}\n\nThis came from another Claude session."),
    ])
    check("a dequeue delivered in the peer wrapper takes the peer message, not the older reply",
          never_read(path) == ["older reply"], never_read(path))

    path = write_transcript(workspace, "wrapper-does-not-read-a-reply.jsonl", [
        *ordinary_records(), enqueue_record("A"),
        user_record(f"Another Claude session sent a message:\nA\n{peer}"),
    ])
    check("the peer wrapper does not count as reading the user's own reply", never_read(path) == ["A"], never_read(path))

    path = write_transcript(workspace, "shell-command-dequeued.jsonl", [
        *ordinary_records(), enqueue_record("typed first, never read"), enqueue_record("./fix.sh"), dequeue_record(),
        user_record("<bash-input>./fix.sh</bash-input>"),
    ])
    check("a dequeue delivered as a shell command takes that command, not the older message",
          never_read(path) == ["typed first, never read"], never_read(path))

    path = write_transcript(workspace, "reply-opens-with-angle-bracket.jsonl", [
        *ordinary_records(), enqueue_record("< 30 minutes is fine"),
    ])
    check("a reply opening with < that is no known tag is kept", never_read(path) == ["< 30 minutes is fine"], never_read(path))

    path = write_transcript(workspace, "short-question-then-queued-answer.jsonl", [
        *ordinary_records(), assistant_record("Approve the short change? A approve, D disapprove."), enqueue_record("A"),
    ])
    output = Path(workspace) / "seat-dialog-0004.md"
    extractor.main(["--transcript-path", str(path), "--output", str(output)])
    tail = output.read_text(encoding="utf-8")
    check("a short final question stays in the tail when an unread reply answers it",
          "Approve the short change?" in tail and tail.index("Approve the short change?") < tail.index(INTRODUCTION), tail)

    path = write_transcript(workspace, "reply-queued-before-short-question.jsonl", [
        *ordinary_records(), assistant_record("Long item 1 question: approve the first change?"), enqueue_record("A"),
        assistant_record("Approve item 2?"),
    ])
    output = Path(workspace) / "seat-dialog-0006.md"
    extractor.main(["--transcript-path", str(path), "--output", str(output)])
    tail = output.read_text(encoding="utf-8")
    check("a reply queued before a short question is shown before it, after the question it answers",
          tail.index("Long item 1 question") < tail.index(INTRODUCTION) < tail.index("Approve item 2?"), tail)

    path = write_transcript(workspace, "removal-without-display-then-equal-notification.jsonl", [
        *ordinary_records(), enqueue_record("human reply"), enqueue_record("N"),
        remove_record("N", "delivered_to_agent"), enqueue_record("N"), dequeue_record(), user_record("N"),
    ])
    check("a delivering removal with no display does not claim a later equal message's display",
          never_read(path) == ["human reply"], never_read(path))

    path = write_transcript(workspace, "two-absorbed-before-their-attachments.jsonl", [
        *ordinary_records(), enqueue_record("A"), enqueue_record("B"), enqueue_record("B"),
        remove_record("A", "absorbed_mid_turn"), remove_record("B", "absorbed_mid_turn"),
        absorbed_attachment_record("A"), absorbed_attachment_record("B"),
    ])
    check("a removal still claims its display past another removal", never_read(path) == ["B"], never_read(path))

    path = write_transcript(workspace, "equal-reply-queued-before-absorbed-attachment.jsonl", [
        *ordinary_records(), enqueue_record("A"), remove_record("A", "absorbed_mid_turn"),
        enqueue_record("A"), absorbed_attachment_record("A"),
    ])
    check("an absorbed removal claims its attachment past an equal message queued after it",
          never_read(path) == ["A"], never_read(path))

    path = write_transcript(workspace, "absorbed-without-attachment-then-equal-dequeued.jsonl", [
        *ordinary_records(), enqueue_record("human reply"), enqueue_record("N"),
        remove_record("N", "absorbed_mid_turn"), enqueue_record("N"), dequeue_record(), user_record("N"),
    ])
    check("an absorbed removal does not claim the user record of a later equal message's dequeue",
          never_read(path) == ["human reply"], never_read(path))

    path = write_transcript(workspace, "dequeue-then-agent-record-then-equal-prompt.jsonl", [
        *ordinary_records(), enqueue_record("A"), enqueue_record("A"), dequeue_record(),
        assistant_record("an agent turn after the dequeue"), user_record("A"),
    ])
    check("a dequeue does not claim an equal user record after the next agent record",
          never_read(path) == [], never_read(path))

    longer_tag_reply = "<agent-message-id> should be required"
    path = write_transcript(workspace, "reply-opens-with-longer-tag-name.jsonl", [
        *ordinary_records(), enqueue_record(longer_tag_reply),
        enqueue_record("<task-notification-id> too"), enqueue_record("<cross-session-message-id> too"),
        enqueue_record('<agent-message from="a1">done</agent-message>'), enqueue_record("<task-notification>\ndone"),
        enqueue_record('<cross-session-message\nfrom="a1">done</cross-session-message>'),
    ])
    check("only a sender tag whose name ends is left out, so a reply opening with a longer tag name is kept",
          never_read(path) == [longer_tag_reply, "<task-notification-id> too", "<cross-session-message-id> too"],
          never_read(path))

    path = write_transcript(workspace, "reply-typed-before-the-first-shown-turn.jsonl", [
        user_record("the question the early reply answers"), assistant_record("Approve the early change?"),
        enqueue_record("early reply"),
        user_record("a later prompt " * 400), assistant_record("a later answer " * 400),
    ])
    output = Path(workspace) / "seat-dialog-0007.md"
    extractor.main(["--transcript-path", str(path), "--output", str(output)])
    tail = output.read_text(encoding="utf-8")
    before_tail_introduction = extractor.CONVERSATION_TAIL_UNREAD_QUEUED_USER_MESSAGE_TYPED_BEFORE_FIRST_SHOWN_TURN_INTRODUCTION_LINE_TEXT
    check("a reply typed before the first shown turn says that what it answers is outside the tail",
          "Approve the early change?" not in tail and f"{before_tail_introduction}\n\nearly reply" in tail
          and INTRODUCTION not in tail, tail)

    # The shape of transcripts 608ae0eb, fcbc9268 and 8fe60f28: Claude Code delivers the peer message without its hop-chain.
    path = write_transcript(workspace, "peer-delivered-without-hop-chain.jsonl", [
        *ordinary_records(), enqueue_record("./command-the-agent-ran.sh"),
        enqueue_record('<cross-session-message from="bridge:session_01" hop-chain="fce1498b" from-name="peer">\n'
                       'merge it\n</cross-session-message>'),
        dequeue_record(),
        user_record('Another Claude session sent a message:\n<cross-session-message from="bridge:session_01" '
                    'from-name="peer">\nmerge it\n</cross-session-message>\n\nThis came from another Claude session.'),
    ])
    check("a dequeue does not match a peer message by ignoring its hop-chain, which would keep a command already run",
          never_read(path) == [], never_read(path))

    path = write_transcript(workspace, "delivered-to-agent-removal-then-equal-attachment.jsonl", [
        *ordinary_records(), enqueue_record("A"), remove_record("A", "delivered_to_agent"),
        enqueue_record("A"), absorbed_attachment_record("A"),
    ])
    check("a delivered_to_agent removal claims no attachment, so the attachment shows the later equal message read",
          never_read(path) == [], never_read(path))

    path = write_transcript(workspace, "short-final-turn-nothing-queued.jsonl", [
        *ordinary_records(), assistant_record("Approve the short change? A approve, D disapprove."),
    ])
    output = Path(workspace) / "seat-dialog-0005.md"
    extractor.main(["--transcript-path", str(path), "--output", str(output)])
    check("with nothing unread, a short final agent turn is still left out",
          "Approve the short change?" not in output.read_text(encoding="utf-8"))

    path = write_transcript(workspace, "all-read.jsonl", [
        *ordinary_records(), enqueue_record("read"), remove_record("read", "absorbed_mid_turn"),
    ])
    output = Path(workspace) / "seat-dialog-0003.md"
    extractor.main(["--transcript-path", str(path), "--output", str(output)])
    check("with nothing unread, the tail has no such turn",
          INTRODUCTION not in output.read_text(encoding="utf-8"))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
