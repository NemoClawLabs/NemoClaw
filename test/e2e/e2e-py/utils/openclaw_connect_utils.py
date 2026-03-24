# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid

import pytest

pexpect = pytest.importorskip("pexpect")


def int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


def strip_ansi(text: str) -> str:
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    text = re.sub(r"\x1b\][^\x07]*(\x07|\x1b\\)", "", text)
    return text.replace("\r", "")


def capture_for_seconds(child: pexpect.spawn, seconds: int) -> str:
    deadline = time.time() + max(seconds, 1)
    chunks: list[str] = []
    while time.time() < deadline:
        try:
            chunk = child.read_nonblocking(size=4096, timeout=1)
            if chunk:
                chunks.append(chunk)
        except pexpect.TIMEOUT:
            continue
        except pexpect.EOF:
            break
    return "".join(chunks)


def extract_reply_candidates(clean_text: str, sent_message: str) -> list[str]:
    ignore_fragments = [
        "openclaw tui",
        "openclaw-tui)",
        "agent main",
        "session main",
        "connected",
        "running",
        "tokens",
        "warning: envhttpproxyagent is experimental",
        "trace-warnings",
        "(node:",
    ]
    lines: list[str] = []
    for raw in clean_text.splitlines():
        line = raw.strip()
        if not line or line == sent_message.strip():
            continue
        if any(fragment in line.lower() for fragment in ignore_fragments):
            continue
        if all(ch in "─-_=|[](){}:;., " for ch in line):
            continue
        lines.append(line)
    return lines


def run_agent_fallback_over_ssh(sandbox: str, message: str, timeout_sec: int) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        ssh_config = tmp.name
    try:
        cfg = subprocess.run(
            ["openshell", "sandbox", "ssh-config", sandbox],
            capture_output=True,
            text=True,
        )
        if cfg.returncode != 0:
            return cfg.returncode, (cfg.stdout or "") + (cfg.stderr or "")
        with open(ssh_config, "w", encoding="utf-8") as f:
            f.write(cfg.stdout or "")

        session_id = f"pytest-{uuid.uuid4().hex[:8]}"
        remote_cmd = (
            f"openclaw agent --agent main --local --session-id '{session_id}' "
            f"-m {shlex.quote(message)}"
        )
        run = subprocess.run(
            [
                "ssh",
                "-T",
                "-F",
                ssh_config,
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "ConnectTimeout=10",
                "-o",
                "LogLevel=ERROR",
                f"openshell-{sandbox}",
                remote_cmd,
            ],
            capture_output=True,
            text=True,
            timeout=max(timeout_sec, 30),
        )
        return run.returncode, (run.stdout or "") + (run.stderr or "")
    finally:
        try:
            os.remove(ssh_config)
        except OSError:
            pass


def spawn_connected_shell(sandbox: str, timeout_sec: int) -> pexpect.spawn:
    child = pexpect.spawn(
        "nemoclaw",
        [sandbox, "connect"],
        encoding="utf-8",
        timeout=timeout_sec,
    )
    child.logfile_read = None
    child.expect([r"\$ ", r"# "], timeout=timeout_sec)
    return child


def close_connected_shell(child: pexpect.spawn) -> None:
    if not child.isalive():
        return
    child.sendcontrol("c")
    try:
        child.expect([r"\$ ", r"# "], timeout=5)
        child.sendline("exit")
    except Exception:
        pass
    child.close(force=True)


@pytest.fixture(scope="module")
def sandbox_name() -> str:
    if shutil.which("nemoclaw") is None:
        pytest.skip("nemoclaw not found on PATH")
    if shutil.which("openshell") is None:
        pytest.skip("openshell not found on PATH")

    sandbox = os.getenv("SANDBOX_NAME") or os.getenv("NEMOCLAW_SANDBOX_NAME") or "e2e-expect-demo"
    probe = subprocess.run(
        ["openshell", "sandbox", "get", sandbox],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        out = (probe.stdout or "") + (probe.stderr or "")
        pytest.skip(f"openshell sandbox '{sandbox}' not ready: {out.strip()[:300]}")
    return sandbox


def param_messages() -> list[str]:
    raw = os.getenv("OPENCLAW_TUI_MESSAGES", "").strip()
    if raw:
        parsed = [m.strip() for m in raw.split(",") if m.strip()]
        if parsed:
            return parsed
    return [
        "who are u",
        "say hello in one line",
        "what can you do?",
    ]
