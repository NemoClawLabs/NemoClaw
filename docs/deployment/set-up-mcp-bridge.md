---
title:
  page: "Bridge MCP Servers into a NemoClaw Sandbox"
  nav: "Set Up MCP Bridge"
description: "Bridge host-side MCP servers into the sandbox so the OpenClaw agent can use external tools without exposing API keys."
keywords: ["NemoClaw mcp bridge", "mcp server sandbox", "mcporter OpenClaw", "model context protocol"]
topics: ["generative_ai", "ai_agents"]
tags: ["OpenClaw", "OpenShell", "mcp", "mcporter", "deployment", "NemoClaw"]
content:
  type: how_to
  difficulty: intermediate
  audience: ["developer", "engineer"]
---

<!--
  SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
  SPDX-License-Identifier: Apache-2.0
-->

# Bridge MCP Servers into a NemoClaw Sandbox

Bridge stdio-based MCP servers from the host into a NemoClaw sandbox so the OpenClaw agent can call external tools without exposing API keys inside the sandbox.

## How It Works

A stdio-to-HTTP proxy runs on the host, spawning the MCP server subprocess with the user's API keys from the host environment.
The proxy port is forwarded into the sandbox via `openshell forward`, appearing as `localhost:<port>` inside the sandbox.
mcporter inside the sandbox connects to the forwarded port as a standard HTTP MCP server.

```text
Host                                Sandbox
+------------------------+         +-----------------------+
|  stdio MCP server      |         |  mcporter             |
|    |                   | forward |    |                  |
|  stdio-to-HTTP proxy   |---------| localhost:<port>      |
|    :3101               |         |                       |
|  API keys stay here    |         |  OpenClaw agent       |
+------------------------+         |    (no API keys)      |
                                   +-----------------------+
```

## Prerequisites

- A running NemoClaw sandbox.
- An MCP server command, for example `npx @modelcontextprotocol/server-github`.
- The required API key exported as an environment variable on the host.

## Add an MCP Server

Export the API key on the host.
The bridge reads the variable name from the host environment and passes it to the MCP server process.
The key never enters the sandbox.

```console
$ export GITHUB_TOKEN=<your-token>
$ nemoclaw <name> mcp add --name github \
    --command "npx @modelcontextprotocol/server-github" \
    --env GITHUB_TOKEN
```

This command:

1. Starts the stdio-to-HTTP proxy on the host with the named environment variables.
2. Forwards the proxy port into the sandbox via `openshell forward`.
3. Installs mcporter in the sandbox if not already present.
4. Registers the server in the sandbox mcporter configuration.

## List Bridges

List all MCP bridges for a sandbox with their running status.

```console
$ nemoclaw <name> mcp list
```

```text
MCP Bridges for sandbox "my-assistant":

  * github      :3101  npx @modelcontextprotocol/server-github      env: GITHUB_TOKEN
  * slack       :3102  npx @anthropic/mcp-server-slack               env: SLACK_TOKEN
```

A green dot indicates a running proxy.
A red dot indicates the proxy has stopped and needs to be restarted.

## Remove a Bridge

Stop the proxy, stop the port forward, and remove the server from the sandbox mcporter configuration.

```console
$ nemoclaw <name> mcp remove github
```

## Restart After Reboot

Proxy processes do not survive a host reboot.
Restart all proxy processes and port forwards from the saved configuration.
The sandbox-side mcporter configuration persists and does not need to be rewritten.

```console
$ nemoclaw <name> mcp restart
```

To restart a single bridge, pass the server name.

```console
$ nemoclaw <name> mcp restart github
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `nemoclaw <name> mcp add --name <id> --command <cmd> [--env VAR ...] [--port PORT]` | Bridge a host MCP server into the sandbox |
| `nemoclaw <name> mcp list` | List bridges with running status |
| `nemoclaw <name> mcp remove <id>` | Stop and remove a bridge |
| `nemoclaw <name> mcp restart [<id>]` | Restart all or one bridge after reboot |

### Flags

`--name <id>`
: Required. Alphanumeric identifier for the MCP server.

`--command <cmd>`
: Required. The command to spawn the MCP server (e.g., `"npx @modelcontextprotocol/server-github"`).

`--env VAR`
: Repeatable. Name of an environment variable to pass from the host to the MCP server process.
  The bridge reads the value from the host environment. The value never enters the sandbox.

`--port PORT`
: Optional. Host port for the proxy (default: auto-assigned from range 3100-3199).

## Manual Setup

The CLI commands above automate these steps.
Use the manual process if you need to customize the proxy or debug the connection.

### Install mcporter

OpenClaw uses [mcporter](https://github.com/steipete/mcporter) to connect to MCP servers.
The sandbox image does not include mcporter, so install it to the writable layer.

```console
$ nemoclaw <name> connect
sandbox@<name>:~$ npm install --prefix /sandbox/.local mcporter
sandbox@<name>:~$ echo 'export PATH="/sandbox/.local/node_modules/.bin:$PATH"' >> /sandbox/.bash_profile
sandbox@<name>:~$ source /sandbox/.bash_profile
sandbox@<name>:~$ mcporter --version
```

This persists across sandbox restarts.
It is lost only if the sandbox is destroyed and recreated.

### Start the Proxy

```console
$ node scripts/mcp-proxy.js \
    --exe npx \
    --arg @modelcontextprotocol/server-github \
    --env GITHUB_TOKEN \
    --port 3101 &
```

### Forward the Port

```console
$ openshell forward start 3101 <name> &
```

### Register in the Sandbox

```console
$ nemoclaw <name> connect
sandbox@<name>:~$ mcporter config add github --url http://localhost:3101 --scope home
sandbox@<name>:~$ mcporter list github
```

If the tool list is returned, the bridge is working.

## Security

| Layer | Protection |
|-------|-----------|
| API keys | Stay in host environment variables. Never written to sandbox filesystem. |
| Proxy binding | Listens on `127.0.0.1` only. Not reachable from the network. |
| Port forward | OpenShell maps the host port to sandbox localhost. No egress policy needed. |
| Sandbox isolation | Filesystem, network, and process policies still enforced by OpenShell. |

## Next Steps

- [Set Up Telegram Bridge](set-up-telegram-bridge.md) for another auxiliary service pattern.
- [Commands](../reference/commands.md) for the full CLI reference.
- [Network Policies](../reference/network-policies.md) for egress control.
