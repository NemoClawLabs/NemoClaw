#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Real interactive NemoClaw install under expect: runs public curl|bash and answers
# nemoclaw onboard prompts (see bin/lib/onboard.js — brittle if copy changes).
#
# Prereq:
#   - expect, curl, Docker (same as normal install)
#   - NVIDIA_API_KEY=nvapi-... in environment when cloud path asks for key (or already in ~/.nemoclaw/credentials.json)
#
# This script unsets NEMOCLAW_NON_INTERACTIVE for the child so onboard stays interactive.
#
# Optional env (answers):
#   INTERACTIVE_SANDBOX_NAME     default: e2e-expect-demo
#   INTERACTIVE_RECREATE_ANSWER  y|n when sandbox exists (default: n)
#   INTERACTIVE_INFERENCE_SEND   sent at "Choose [N]:" (default: empty = Enter = cloud default)
#   INTERACTIVE_MODEL_SEND       sent at "Choose model [1]:" (default: Enter)
#   INTERACTIVE_PRESETS_SEND     sent at "Apply suggested presets" (default: y)
#   NEMOCLAW_INSTALL_SCRIPT_URL  default: https://www.nvidia.com/nemoclaw.sh
#
# Offline / no-network smoke of expect only:
#   DEMO_FAKE_ONLY=1 bash .../expect-interactive-install.sh

set -euo pipefail

if ! command -v expect >/dev/null 2>&1; then
  echo "ERROR: expect not on PATH." >&2
  exit 1
fi

export NEMOCLAW_INSTALL_SCRIPT_URL="${NEMOCLAW_INSTALL_SCRIPT_URL:-https://www.nvidia.com/nemoclaw.sh}"

if [[ "${DEMO_FAKE_ONLY:-0}" == "1" ]]; then
  fake_installer="$(mktemp)"
  trap 'rm -f "$fake_installer"' EXIT
  cat >"$fake_installer" <<'INSTALLER'
#!/bin/bash
set -e
read -r -p "Continue with demo install? [y/N]: " a
[[ "${a:-}" =~ ^[yY] ]] || exit 1
read -r -p "Sandbox name: " name
echo "Using sandbox: ${name:-demo-sandbox}"
read -r -p "Proceed? [y/N]: " b
[[ "${b:-}" =~ ^[yY] ]] || exit 1
echo "INSTALL_DEMO_OK"
INSTALLER
  chmod +x "$fake_installer"
  expect <<EOF
set timeout 30
spawn bash "$fake_installer"
expect {
  -re {Continue with demo install} { send "y\r"; exp_continue }
  -re {Sandbox name:}             { send "e2e-demo-sandbox\r"; exp_continue }
  -re {Proceed\\?}               { send "y\r"; exp_continue }
  "INSTALL_DEMO_OK"             { exit 0 }
  timeout                       { exit 1 }
  eof                           { exit 0 }
}
EOF
  echo "DEMO_FAKE_ONLY OK"
  exit 0
fi

# Real install: require API key in env if onboard will prompt (no key in creds file).
if [[ -z "${NVIDIA_API_KEY:-}" ]]; then
  echo "WARN: NVIDIA_API_KEY is not set. If ~/.nemoclaw/credentials.json has no key," >&2
  echo "      onboard will prompt — expect will fail unless you export NVIDIA_API_KEY." >&2
fi

export INTERACTIVE_SANDBOX_NAME="${INTERACTIVE_SANDBOX_NAME:-e2e-expect-demo}"
export INTERACTIVE_RECREATE_ANSWER="${INTERACTIVE_RECREATE_ANSWER:-n}"
export INTERACTIVE_INFERENCE_SEND="${INTERACTIVE_INFERENCE_SEND:-}"
export INTERACTIVE_MODEL_SEND="${INTERACTIVE_MODEL_SEND:-}"
export INTERACTIVE_PRESETS_SEND="${INTERACTIVE_PRESETS_SEND:-y}"

echo "Starting REAL install: curl | bash (interactive onboard, expect-driven answers)."
echo "  URL:    $NEMOCLAW_INSTALL_SCRIPT_URL"
echo "  SANDBOX=$INTERACTIVE_SANDBOX_NAME"
echo "  This can take many minutes. Prefer CI: NEMOCLAW_NON_INTERACTIVE=1 without expect."
echo ""

# shellcheck disable=SC2016
expect <<'EXPECT'
set timeout -1

if {![info exists env(NEMOCLAW_INSTALL_SCRIPT_URL)]} {
  set url "https://www.nvidia.com/nemoclaw.sh"
} else {
  set url $env(NEMOCLAW_INSTALL_SCRIPT_URL)
}

set sandbox $env(INTERACTIVE_SANDBOX_NAME)
set recreate $env(INTERACTIVE_RECREATE_ANSWER)
set infer_send $env(INTERACTIVE_INFERENCE_SEND)
set model_send $env(INTERACTIVE_MODEL_SEND)
set presets_send $env(INTERACTIVE_PRESETS_SEND)

if {![info exists env(NVIDIA_API_KEY)]} {
  set apikey ""
} else {
  set apikey $env(NVIDIA_API_KEY)
}

log_user 1

# Pipe install: install.sh reattaches onboard to /dev/tty when stdin is not a TTY.
spawn bash -c "exec 3<>/dev/tty; unset NEMOCLAW_NON_INTERACTIVE; export NEMOCLAW_NON_INTERACTIVE=; curl -fsSL \"$url\" | bash"

expect {
  eof { exit 0 }

  -re {Sandbox name \(lowercase} {
    send "$sandbox\r"
    exp_continue
  }

  -re {already exists\. Recreate\?} {
    send "$recreate\r"
    exp_continue
  }

  # Provider menu: "  Choose [N]: " (only when multiple inference options; skip if not shown)
  -re {Choose \[[0-9]+\]: } {
    send "$infer_send\r"
    exp_continue
  }

  -re {NVIDIA API Key:} {
    if {$apikey eq ""} {
      puts stderr "expect: got NVIDIA API Key prompt but NVIDIA_API_KEY is empty"
      exit 1
    }
    send "$apikey\r"
    exp_continue
  }

  -re {Choose model} {
    send "$model_send\r"
    exp_continue
  }

  -re {Apply suggested presets} {
    send "$presets_send\r"
    exp_continue
  }

  -re {Enter preset names} {
    send "pypi,npm\r"
    exp_continue
  }

  timeout {
    puts stderr "expect: unexpected timeout"
    exit 1
  }
}
EXPECT

echo ""
echo "Expect session ended (installer finished or exited)."
