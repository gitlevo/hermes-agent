"""mooxi patch: ``approvals.allow_yolo: false`` makes every YOLO surface inert (MOOXI-PATCHES.md).

With the switch off, ``/yolo`` (gateway and the shared toggle), a persisted or launch-seeded session bypass
and the process ``--yolo`` / ``HERMES_YOLO_MODE`` never skip an approval. Default (true) is upstream."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import gateway.run as gateway_run
from gateway.config import Platform
from gateway.platforms.event import MessageEvent
from gateway.session import SessionSource
from tools import approval, approval_context
from tools.approval_yolo import apply_launch_yolo, restore_gateway_yolo, restore_session_yolo, toggle_session_yolo

KEY = "agent:main:telegram:dm:chat-a"


@pytest.fixture
def allow(monkeypatch):
    """allow(False) sets approvals.allow_yolo: false for the rest of the test."""
    monkeypatch.setattr(approval, "_YOLO_MODE_FROZEN", False)
    monkeypatch.delenv("HERMES_YOLO_MODE", raising=False)

    def set_allowed(value):
        monkeypatch.setattr(approval_context, "_get_approval_config", lambda: {"mode": "manual", "allow_yolo": value})
    yield set_allowed
    approval.clear_session(KEY)


def test_default_is_upstream_behaviour(allow, monkeypatch):
    monkeypatch.setattr(approval_context, "_get_approval_config", dict)
    assert approval_context.yolo_allowed() is True
    assert toggle_session_yolo(KEY) is True and approval.is_session_yolo_enabled(KEY)


def test_toggle_does_nothing_and_clears_a_stored_on(allow):
    allow(False)
    stored = []
    assert toggle_session_yolo(KEY, persist=stored.append) is False
    assert toggle_session_yolo(KEY, True, persisted=True, persist=stored.append) is False
    assert stored == [False, False]
    assert not approval.is_session_yolo_enabled(KEY)
    assert not approval.is_approval_bypass_active_for_session(KEY)


def test_restored_and_launch_seeded_bypasses_are_inert(allow):
    allow(False)
    assert restore_session_yolo(KEY, True) is False
    apply_launch_yolo(KEY)
    restore_gateway_yolo(KEY + "-2", True)  # writes the set directly; the read side still refuses it
    for key in (KEY, KEY + "-2"):
        assert not approval.is_session_yolo_enabled(key)
        assert not approval.is_approval_bypass_active_for_session(key)
    approval.clear_session(KEY + "-2")


def test_a_bypass_set_before_the_switch_turned_off_is_revoked(allow):
    allow(True)
    assert toggle_session_yolo(KEY) is True
    allow(False)
    assert not approval.is_session_yolo_enabled(KEY)
    assert not approval.is_approval_bypass_active_for_session(KEY)


def test_process_yolo_is_revoked_live(allow, monkeypatch):
    monkeypatch.setattr(approval, "_YOLO_MODE_FROZEN", True)
    allow(True)
    assert approval.is_approval_bypass_active_for_session("") is True
    allow(False)
    assert approval.is_approval_bypass_active_for_session("") is False
    assert approval._yolo_active() is False


def test_process_yolo_env_is_voided_at_import(tmp_path):
    """--yolo sets HERMES_YOLO_MODE before tools.approval is imported; with allow_yolo false the frozen flag
    (which hosted-room policy and session rows read directly) comes out False."""
    home = tmp_path / "home"
    home.mkdir()
    root = Path(__file__).resolve().parents[2]
    code = "from tools import approval; print(approval._YOLO_MODE_FROZEN)"
    out = {}
    for name, cfg in (("off", "approvals:\n  allow_yolo: false\n"), ("on", "approvals:\n  allow_yolo: true\n")):
        (home / "config.yaml").write_text(cfg)
        env = {**os.environ, "HERMES_HOME": str(home), "HERMES_YOLO_MODE": "1"}
        out[name] = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True,
                                   text=True, check=True).stdout.strip().splitlines()[-1]
    assert out == {"off": "False", "on": "True"}


@pytest.mark.asyncio
async def test_gateway_yolo_command_says_it_is_off(allow):
    allow(False)
    runner = object.__new__(gateway_run.GatewayRunner)
    runner.session_store = None
    runner.config = None
    source = SessionSource(platform=Platform.TELEGRAM, user_id="user-chat-a", chat_id="chat-a",
                           user_name="tester", chat_type="dm")
    reply = await runner._handle_yolo_command(MessageEvent(text="/yolo", source=source))
    assert "allow_yolo: false" in str(getattr(reply, "text", reply))
    assert not approval.is_session_yolo_enabled(runner._session_key_for_source(source))
