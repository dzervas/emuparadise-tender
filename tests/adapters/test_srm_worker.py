"""The SRM writer must never overlap Steam; session recovery runs on failure."""

import json
import subprocess
from unittest.mock import Mock

import pytest

from adapters import srm_worker


@pytest.mark.parametrize("failure", [None, "steam_alive", "srm_failure", "timeout"])
def test_session_order_and_recovery(monkeypatch, tmp_path, failure):
    calls = []
    monkeypatch.setattr(srm_worker, "command", lambda args, **kw: calls.append(args))
    monkeypatch.setattr(
        srm_worker.subprocess, "run", lambda *a, **kw: Mock(returncode=0 if failure == "steam_alive" else 1)
    )
    process = Mock(pid=1234)
    process.wait.side_effect = (
        [subprocess.TimeoutExpired("srm", 900), 0]
        if failure == "timeout"
        else [1 if failure == "srm_failure" else 0, 0]
    )

    def spawn(args, **kwargs):
        calls.append(args)
        return process

    monkeypatch.setattr(srm_worker.subprocess, "Popen", spawn)
    monkeypatch.setattr(srm_worker.os, "killpg", lambda pid, sig: calls.append(["kill-writer-group"]))
    path = tmp_path / "status.json"
    srm_worker.run_job({"session": "gamescope-session.service", "srm": "/srm", "xvfb": "/xvfb-run"}, path)
    assert calls[0] == ["systemctl", "--user", "stop", "gamescope-session.service"]
    assert calls[-1] == ["systemctl", "--user", "start", "gamescope-session.service"]
    if failure == "steam_alive":
        assert len(calls) == 2
    else:
        assert calls[1] == ["/xvfb-run", "-a", "/srm", "add"]
        assert calls[-2] == ["kill-writer-group"]
    assert json.loads(path.read_text())["status"] == ("failed" if failure else "completed")


def test_failed_restart_is_reported(monkeypatch, tmp_path):
    def execute(args, **kwargs):
        raise RuntimeError("session unavailable")

    monkeypatch.setattr(srm_worker, "command", execute)
    path = tmp_path / "status.json"
    srm_worker.run_job({"session": "gamescope-session.service"}, path)
    status = json.loads(path.read_text())
    assert status["status"] == "failed"
    assert "Game Mode restart failed" in status["message"]
