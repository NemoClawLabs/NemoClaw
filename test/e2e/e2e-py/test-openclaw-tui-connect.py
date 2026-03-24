# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Pytest e2e for OpenClaw through `nemoclaw <sandbox> connect`.

Cases:
  1) connect + run an OpenClaw command (`openclaw status`)
  2) connect + open `openclaw tui` + send parameterized prompts

Environment:
  SANDBOX_NAME or NEMOCLAW_SANDBOX_NAME  (default: test01)
  OPENCLAW_CONNECT_TIMEOUT               (default: 120)
  OPENCLAW_TUI_BOOT_TIMEOUT              (default: 180)
  OPENCLAW_TUI_REPLY_TIMEOUT             (default: 240)
  OPENCLAW_TUI_CAPTURE_SECONDS           (default: 20)
  OPENCLAW_TUI_MESSAGES                  (optional comma-separated prompts)
"""

from __future__ import annotations

import re

import pytest

from utils.openclaw_connect_utils import (
    capture_for_seconds,
    close_connected_shell,
    extract_reply_candidates,
    int_env,
    param_messages,
    run_agent_fallback_over_ssh,
    sandbox_name,
    spawn_connected_shell,
    strip_ansi,
)


@pytest.mark.e2e
def test_connect_can_run_openclaw_status(sandbox_name: str) -> None:
    connect_timeout = int_env("OPENCLAW_CONNECT_TIMEOUT", 120)
    child = spawn_connected_shell(sandbox_name, connect_timeout)
    try:
        child.sendline("openclaw status")
        child.expect([r"\$ ", r"# "], timeout=30)
        out = strip_ansi((child.before or "")[-2000:])
        assert out.strip(), "openclaw status produced no output"
        assert "openclaw" in out.lower() or "status" in out.lower() or "agent" in out.lower()
    finally:
        close_connected_shell(child)


@pytest.mark.e2e
@pytest.mark.parametrize("message", param_messages())
def test_openclaw_tui_can_send_messages(sandbox_name: str, message: str) -> None:
    connect_timeout = int_env("OPENCLAW_CONNECT_TIMEOUT", 120)
    boot_timeout = int_env("OPENCLAW_TUI_BOOT_TIMEOUT", 180)
    reply_timeout = int_env("OPENCLAW_TUI_REPLY_TIMEOUT", 240)
    capture_seconds = int_env("OPENCLAW_TUI_CAPTURE_SECONDS", 20)

    child = spawn_connected_shell(sandbox_name, connect_timeout)
    try:
        child.sendline("openclaw tui")
        child.expect(
            [r"OpenClaw", r"openclaw tui", r"agent main", r"session main", r"connected"],
            timeout=boot_timeout,
        )

        child.sendline(message)
        child.expect(
            [r"running", r"connected", r"agent main", r"session main", re.escape(message)],
            timeout=reply_timeout,
        )

        captured = capture_for_seconds(child, capture_seconds)
        raw_tail = captured[-3000:] if captured else (child.before or "")[-3000:]
        clean_tail = strip_ansi(raw_tail)
        candidates = extract_reply_candidates(clean_tail, message)

        print(f"\n----- TUI raw tail (message={message!r}) -----")
        print(raw_tail)
        print("----- End TUI raw tail -----")
        print("----- TUI reply candidates -----")
        print("\n".join(candidates[-8:]) if candidates else "(none)")
        print("----- End TUI reply candidates -----\n")

        if not clean_tail.strip():
            raise AssertionError(f"No TUI output captured after sending {message!r}.")
        if candidates:
            return

        rc, agent_out = run_agent_fallback_over_ssh(sandbox_name, message, reply_timeout)
        clean_agent = strip_ansi(agent_out)
        agent_candidates = extract_reply_candidates(clean_agent, message)
        print("----- Agent fallback output (trimmed) -----")
        print(clean_agent[-3000:])
        print("----- End agent fallback output -----")
        print("----- Agent fallback reply candidates -----")
        print("\n".join(agent_candidates[-8:]) if agent_candidates else "(none)")
        print("----- End agent fallback reply candidates -----")

        if rc != 0:
            raise AssertionError(f"TUI reply not captured and agent fallback failed (exit {rc}).")
        if not agent_candidates:
            raise AssertionError(
                "TUI reply not captured and agent fallback had no assistant-like reply lines."
            )
    finally:
        close_connected_shell(child)
