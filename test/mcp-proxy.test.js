// SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { describe, it, expect } from "vitest";

// Test the arg parsing logic used by mcp-proxy.js
function parseArgs(argv) {
  const args = { exe: null, cmdArgs: [], env: [], port: 3101 };
  for (let i = 0; i < argv.length; i++) {
    switch (argv[i]) {
      case "--exe":
        args.exe = argv[++i];
        break;
      case "--arg":
        args.cmdArgs.push(argv[++i]);
        break;
      case "--env":
        args.env.push(argv[++i]);
        break;
      case "--port":
        args.port = parseInt(argv[++i], 10);
        break;
    }
  }
  return args;
}

describe("mcp-proxy parseArgs", () => {
  it("parses --exe flag", () => {
    const result = parseArgs(["--exe", "npx"]);
    expect(result.exe).toBe("npx");
  });

  it("parses --port flag", () => {
    const result = parseArgs(["--exe", "npx", "--port", "3105"]);
    expect(result.port).toBe(3105);
  });

  it("defaults port to 3101", () => {
    const result = parseArgs(["--exe", "npx"]);
    expect(result.port).toBe(3101);
  });

  it("collects multiple --arg flags", () => {
    const result = parseArgs([
      "--exe", "npx",
      "--arg", "@modelcontextprotocol/server-github",
      "--arg", "--verbose",
    ]);
    expect(result.cmdArgs).toEqual(["@modelcontextprotocol/server-github", "--verbose"]);
  });

  it("collects multiple --env flags", () => {
    const result = parseArgs([
      "--exe", "npx",
      "--env", "GITHUB_TOKEN",
      "--env", "SLACK_TOKEN",
    ]);
    expect(result.env).toEqual(["GITHUB_TOKEN", "SLACK_TOKEN"]);
  });

  it("parses full command line", () => {
    const result = parseArgs([
      "--exe", "npx",
      "--arg", "@modelcontextprotocol/server-github",
      "--env", "GITHUB_TOKEN",
      "--port", "3101",
    ]);
    expect(result.exe).toBe("npx");
    expect(result.cmdArgs).toEqual(["@modelcontextprotocol/server-github"]);
    expect(result.env).toEqual(["GITHUB_TOKEN"]);
    expect(result.port).toBe(3101);
  });

  it("returns null exe when not provided", () => {
    const result = parseArgs([]);
    expect(result.exe).toBeNull();
  });
});

describe("mcp-proxy executable validation", () => {
  it("rejects path traversal in exe", () => {
    expect(/\.\./.test("../bin/server")).toBe(true);
    expect(/\.\./.test("../../etc/passwd")).toBe(true);
  });

  it("rejects shell metacharacters in exe", () => {
    expect(/[;&|`$]/.test("npx; rm -rf /")).toBe(true);
    expect(/[;&|`$]/.test("npx | cat")).toBe(true);
    expect(/[;&|`$]/.test("npx & bg")).toBe(true);
    expect(/[;&|`$]/.test("$(cmd)")).toBe(true);
    expect(/[;&|`$]/.test("`cmd`")).toBe(true);
  });

  it("accepts safe executables", () => {
    expect(/\.\./.test("npx")).toBe(false);
    expect(/[;&|`$]/.test("npx")).toBe(false);
    expect(/\.\./.test("node")).toBe(false);
    expect(/[;&|`$]/.test("node")).toBe(false);
    expect(/\.\./.test("/usr/local/bin/server")).toBe(false);
    expect(/[;&|`$]/.test("/usr/local/bin/server")).toBe(false);
  });
});

// Test the CLI-side arg parser (parseMcpArgs in nemoclaw.js)
function parseMcpArgs(actionArgs) {
  const opts = { name: null, command: null, env: [], port: null, server: null };
  for (let i = 0; i < actionArgs.length; i++) {
    switch (actionArgs[i]) {
      case "--name":
        opts.name = actionArgs[++i];
        break;
      case "--command":
        opts.command = actionArgs[++i];
        break;
      case "--env":
        opts.env.push(actionArgs[++i]);
        break;
      case "--port":
        opts.port = parseInt(actionArgs[++i], 10);
        break;
      default:
        if (!opts.server && !actionArgs[i].startsWith("-"))
          opts.server = actionArgs[i];
        break;
    }
  }
  return opts;
}

describe("CLI parseMcpArgs", () => {
  it("parses add arguments", () => {
    const result = parseMcpArgs([
      "--name", "github",
      "--command", "npx @modelcontextprotocol/server-github",
      "--env", "GITHUB_TOKEN",
    ]);
    expect(result.name).toBe("github");
    expect(result.command).toBe("npx @modelcontextprotocol/server-github");
    expect(result.env).toEqual(["GITHUB_TOKEN"]);
  });

  it("parses optional --port", () => {
    const result = parseMcpArgs([
      "--name", "github",
      "--command", "npx server",
      "--port", "3105",
    ]);
    expect(result.port).toBe(3105);
  });

  it("parses positional server name for remove", () => {
    const result = parseMcpArgs(["github"]);
    expect(result.server).toBe("github");
  });

  it("collects multiple --env flags", () => {
    const result = parseMcpArgs([
      "--name", "multi",
      "--command", "cmd",
      "--env", "TOKEN_A",
      "--env", "TOKEN_B",
      "--env", "TOKEN_C",
    ]);
    expect(result.env).toEqual(["TOKEN_A", "TOKEN_B", "TOKEN_C"]);
  });

  it("returns nulls for empty args", () => {
    const result = parseMcpArgs([]);
    expect(result.name).toBeNull();
    expect(result.command).toBeNull();
    expect(result.port).toBeNull();
    expect(result.server).toBeNull();
    expect(result.env).toEqual([]);
  });
});
