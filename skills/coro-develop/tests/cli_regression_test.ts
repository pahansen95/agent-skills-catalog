import assert from "node:assert/strict";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const skill = fileURLToPath(new URL("../", import.meta.url));
const launcher = join(skill, "scripts", "coro");
const fixture = fileURLToPath(new URL("./fixtures/claude.ts", import.meta.url));
type Json = Record<string, unknown>;
const decode = (bytes: Uint8Array) => new TextDecoder().decode(bytes);
const readJson = (path: string) => JSON.parse(Deno.readTextFileSync(path));
const readLines = (path: string): Json[] =>
  Deno.readTextFileSync(path).split(/\r?\n/).filter((s) => s.trim()).map((s) => JSON.parse(s));

async function project(fn: (p: Project) => Promise<void>) {
  const temp = Deno.makeTempDirSync({ prefix: "coro-cli-" });
  try {
    const root = join(temp, "project");
    const bin = join(temp, "bin");
    Deno.mkdirSync(join(root, ".cache", "coro"), { recursive: true });
    Deno.mkdirSync(bin);
    const shim = join(bin, "claude");
    Deno.writeTextFileSync(
      shim,
      '#!/bin/sh\nexec "$CORO_TEST_DENO" run --no-config --allow-env --allow-read --allow-write "$CORO_TEST_FIXTURE" "$@"\n',
    );
    Deno.chmodSync(shim, 0o755);
    const env = Deno.env.toObject();
    for (const key of Object.keys(env)) {
      if (
        key.startsWith("CORO_") || [
          "API_TIMEOUT_MS",
          "BASH_MAX_TIMEOUT_MS",
          "CLAUDE_CODE_DISABLE_1M_CONTEXT",
        ].includes(key)
      ) delete env[key];
    }
    Object.assign(env, {
      PATH: bin + ":" + env.PATH,
      LC_ALL: "C",
      CORO_PROJECT: root,
      CORO_TEST_DENO: Deno.execPath(),
      CORO_TEST_FIXTURE: fixture,
      CORO_TEST_CAPTURE: join(root, "calls.jsonl"),
    });
    const p = {
      root,
      env,
      async call(args: string[], input = "", extra: Record<string, string> = {}) {
        const child = new Deno.Command(launcher, {
          args,
          cwd: root,
          env: { ...env, ...extra },
          clearEnv: true,
          stdin: "piped",
          stdout: "piped",
          stderr: "piped",
        }).spawn();
        const output = child.output();
        const writer = child.stdin.getWriter();
        await writer.write(new TextEncoder().encode(input));
        await writer.close();
        const result = await output;
        return { code: result.code, out: decode(result.stdout), err: decode(result.stderr) };
      },
    };
    await fn(p);
  } finally {
    Deno.removeSync(temp, { recursive: true });
  }
}
type Project = {
  root: string;
  env: Record<string, string>;
  call: (
    args: string[],
    input?: string,
    extra?: Record<string, string>,
  ) => Promise<{ code: number; out: string; err: string }>;
};
function seed(p: Project, slug = "fixture_1700000000", body = "YIELD: CHECK | baseline") {
  const dir = join(p.root, ".cache", "coro", slug);
  Deno.mkdirSync(join(dir, "turns"), { recursive: true });
  Deno.writeTextFileSync(join(dir, "uuid"), "11111111-2222-4333-8444-555555555555\n");
  Deno.writeTextFileSync(join(dir, "meta"), '{"model": "sonnet"}\n');
  Deno.writeTextFileSync(join(p.root, ".cache", "coro", "CURRENT"), slug + "\n");
  Deno.writeTextFileSync(
    join(dir, "turns", "000.jsonl"),
    [
      JSON.stringify({ type: "assistant", message: { content: [{ type: "text", text: body }] } }),
      JSON.stringify({
        type: "result",
        total_cost_usd: 0.25,
        usage: {
          input_tokens: 200,
          cache_read_input_tokens: 300,
          cache_creation_input_tokens: 400,
          output_tokens: 50,
        },
      }),
    ].join("\n") + "\n",
  );
  return dir;
}
const successful = (r: { code: number; err: string }) => assert.equal(r.code, 0, r.err);

Deno.test("CLI resumes Python-format state with exact payload and invocation defaults", () =>
  project(async (p) => {
    const dir = seed(p);
    const r = await p.call(["send", "fixture"], "  inspect résumé 🧪  ");
    successful(r);
    assert.equal(r.out, "résumé 🧪\nYIELD: DONE | checked");
    assert.match(r.err, /resuming fixture_1700000000 turn=1 model=sonnet effort=high/);
    const calls = readLines(join(p.root, "calls.jsonl"));
    assert.deepEqual(calls[0].payload, {
      type: "user",
      message: { role: "user", content: "inspect résumé 🧪" },
    });
    assert.equal(calls[0].timeout, "1200000");
    assert.equal(calls[0].bashTimeout, "1200000");
    assert.equal(calls[0].cwd, Deno.realPathSync(p.root));
    const args = calls[0].args as string[];
    assert.equal(args[args.indexOf("--resume") + 1], "11111111-2222-4333-8444-555555555555");
    assert.equal(args[args.indexOf("--effort") + 1], "high");
    assert(args.includes("--dangerously-skip-permissions"));
    assert.equal(readLines(join(dir, "turns", "001.jsonl")).length, 3);
    assert.equal(
      Deno.readTextFileSync(join(dir, "uuid")).trim(),
      args[args.indexOf("--resume") + 1],
    );
  }));

Deno.test("CLI preserves explicit subprocess defaults and emits tool progress", () =>
  project(async (p) => {
    seed(p);
    const r = await p.call(["send"], "read", {
      CORO_TEST_MODE: "tools",
      API_TIMEOUT_MS: "",
      BASH_MAX_TIMEOUT_MS: "300000",
      CORO_ADD_DIRS: " /tmp/one : : /tmp/two ",
      CORO_EFFORT: "low",
    });
    successful(r);
    assert.match(r.err, /tool_use: Read\(path\)/);
    assert.match(r.err, /tool_result: abcdefghijkl/);
    const call = readLines(join(p.root, "calls.jsonl"))[0];
    assert.equal(call.timeout, "");
    assert.equal(call.bashTimeout, "300000");
    const args = call.args as string[];
    assert.equal(args[args.indexOf("--effort") + 1], "low");
    assert.deepEqual(args.filter((_, i) => args[i - 1] === "--add-dir"), ["/tmp/one", "/tmp/two"]);
  }));

Deno.test("CLI creates a resumable session and suppresses preamble text", () =>
  project(async (p) => {
    const r = await p.call(["create", "phase"]);
    successful(r);
    const slug = r.out.trim();
    assert.match(slug, /^phase_\d+$/);
    const dir = join(p.root, ".cache", "coro", slug);
    assert.deepEqual(readJson(join(dir, "meta")), { model: "sonnet" });
    const id = Deno.readTextFileSync(join(dir, "uuid")).trim();
    assert.match(id, /^[0-9a-f-]{36}$/);
    assert.equal(Deno.readTextFileSync(join(p.root, ".cache", "coro", "CURRENT")).trim(), slug);
    const calls = readLines(join(p.root, "calls.jsonl"));
    assert.equal(calls.length, 1);
    const payload = calls[0].payload as { message: { content: string } };
    assert.equal(
      payload.message.content,
      "/salience on\n\n" + Deno.readTextFileSync(join(skill, "role", "worker.md")).trim() +
        "\n\nAcknowledge this role and wait for your first instruction.",
    );
    assert.match(r.err, /\[coroutine\] YIELD: DONE/);
    assert.equal(readLines(join(dir, "turns", "000.jsonl")).length, 3);
  }));

for (const mode of ["normal", "inline-budget", "no-yield"]) {
  Deno.test("CLI retains deprecated create inline input: " + mode, () =>
    project(async (p) => {
      const r = await p.call(["create", "inline"], "first request", {
        CORO_TEST_MODE: mode,
        CORO_MAX_BUDGET_USD: "0.1",
      });
      successful(r);
      assert.match(r.err, /deprecated/);
      assert.match(r.err, /sending initial content turn=1/);
      const calls = readLines(join(p.root, "calls.jsonl"));
      assert.equal(calls.length, 2);
      assert.deepEqual(calls[1].payload, {
        type: "user",
        message: { role: "user", content: "first request" },
      });
      if (mode === "inline-budget") assert.match(r.err, /turn exceeded.*session remains usable/);
      if (mode === "no-yield") assert.match(r.err, /turn 1 has no YIELD/);
    }));
}

for (const mode of ["budget", "error"]) {
  Deno.test(
    "CLI failed create preserves audit logs and removes bookkeeping: " + mode,
    () =>
      project(async (p) => {
        const r = await p.call(["create", "failure"], "", {
          CORO_TEST_MODE: mode,
          CORO_MAX_BUDGET_USD: "0.1",
        });
        assert.equal(r.code, 1);
        assert.equal(r.out, "");
        assert.match(
          r.err,
          mode === "budget" ? /budget of \$0.1 exceeded \(spent \$0.1250\)/ : /fixture failure/,
        );
        const dirs = [...Deno.readDirSync(join(p.root, ".cache", "coro"))].filter((e) =>
          e.isDirectory
        );
        assert.equal(dirs.length, 1);
        const dir = join(p.root, ".cache", "coro", dirs[0].name);
        assert.throws(() => Deno.statSync(join(dir, "uuid")), Deno.errors.NotFound);
        assert.throws(() => Deno.statSync(join(dir, "meta")), Deno.errors.NotFound);
        assert.equal(readLines(join(dir, "turns", "000.jsonl")).length, 3);
        assert.equal(Deno.readTextFileSync(join(p.root, ".cache", "coro", "CURRENT")), "");
      }),
  );
}

Deno.test("CLI reports assigned/reported UUID mismatch while preserving assigned identity", () =>
  project(async (p) => {
    const r = await p.call(["create", "mismatch"], "", { CORO_TEST_MODE: "mismatch" });
    successful(r);
    assert.match(r.err, /reported session_id.*but we assigned/);
    assert.notEqual(
      Deno.readTextFileSync(join(p.root, ".cache", "coro", r.out.trim(), "uuid")).trim(),
      "different-uuid",
    );
  }));

Deno.test("CLI hold state distinguishes empty reason, cleared state, and automatic resume", () =>
  project(async (p) => {
    const dir = seed(p);
    successful(await p.call(["hold", "fixture", "review", "needed"]));
    assert.match((await p.call(["status"])).out, /hold: {5}yes — review needed/);
    const resumed = await p.call(["send"], "continue");
    successful(resumed);
    assert.match(resumed.err, /cleared hold.*reason: review needed/);
    assert.throws(() => Deno.statSync(join(dir, "hold")), Deno.errors.NotFound);
    successful(await p.call(["hold", "fixture"]));
    assert.equal((await p.call(["unhold"])).out, "unheld session fixture_1700000000\n");
    assert.match((await p.call(["unhold"])).out, /was not held/);
  }));

Deno.test("CLI send budget is soft failure and status exposes budget and all usage counters", () =>
  project(async (p) => {
    seed(p);
    const r = await p.call(["send"], "work", {
      CORO_TEST_MODE: "budget",
      CORO_MAX_BUDGET_USD: "0.1",
    });
    successful(r);
    assert.match(r.err, /session remains usable/);
    const status = await p.call(["status"], "", {
      CORO_MAX_BUDGET_USD: "0.1",
      CORO_TOKEN_WARN: "0",
      CORO_COST_WARN: "0",
    });
    successful(status);
    assert.match(status.out, /600 in \/ 25 out \(cap 64000\)/);
    assert.match(status.out, /cost: {5}\$0.3750 total/);
    assert.match(status.out, /budget: {3}EXCEEDED/);
    assert.match(status.err, /last turn used 600 input tokens/);
    assert.match(status.err, /session cost/);
  }));

Deno.test("CLI warns for missing YIELD and renders the last output line", () =>
  project(async (p) => {
    seed(p);
    const r = await p.call(["send"], "work", { CORO_TEST_MODE: "no-yield" });
    successful(r);
    assert.match(r.err, /turn 1 has no YIELD.*protocol violation/);
    const status = await p.call(["status"]);
    assert.match(status.out, /\(no YIELD signal in turn 1\) last: plain response/);
    assert.match(status.err, /protocol violation/);
    assert.match((await p.call(["turns"])).out, /\(no yield\) plain response/);
  }));

Deno.test("CLI preserves legacy USER_HOLD display and model runtime cap warning", () =>
  project(async (p) => {
    const dir = seed(p, "fixture_1700000000", "YIELD: USER_HOLD | need input");
    const events = readLines(join(dir, "turns", "000.jsonl"));
    Object.assign(events[1], {
      modelUsage: { fixture: { contextWindow: 1000000, maxOutputTokens: 1000 } },
    });
    Deno.writeTextFileSync(
      join(dir, "turns", "000.jsonl"),
      events.map((e) => JSON.stringify(e)).join("\n") + "\n",
    );
    const r = await p.call(["status"]);
    successful(r);
    assert.match(r.out, /YIELD: BLOCKED.*legacy USER_HOLD/);
    assert.match(r.err, /legacy USER_HOLD/);
    assert.match(r.err, /runtime max-output cap is 1000/);
  }));

Deno.test("CLI log/turns/stack operations remain compatible", () =>
  project(async (p) => {
    const dir = seed(p);
    assert.equal(
      (await p.call(["log"])).out,
      Deno.readTextFileSync(join(dir, "turns", "000.jsonl")),
    );
    assert.equal((await p.call(["log", "fixture", "0"])).code, 0);
    assert.match((await p.call(["turns"])).out, /turn 000.*\(preamble\)/);
    assert.match((await p.call(["use", "fixture"])).err, /pushed fixture_1700000000/);
    assert.equal((await p.call(["list"])).out, "fixture_1700000000\nfixture_1700000000\n");
    for (let i = 0; i < 2; i++) assert.equal((await p.call(["pop"])).out, "fixture_1700000000\n");
    assert.equal((await p.call(["pop"])).code, 1);
    assert.equal((await p.call(["list"])).out, "(empty)\n");
    assert.match((await p.call(["status"])).err, /CURRENT stack is empty/);
    assert.equal((await p.call(["log", "fixture", "999"])).code, 1);
  }));

Deno.test("CLI rejects ambiguous sessions and stale CURRENT for mutations", () =>
  project(async (p) => {
    seed(p);
    seed(p, "fixture_1700000001");
    const r = await p.call(["send", "fixture"], "work");
    assert.equal(r.code, 1);
    assert.match(r.err, /ambiguous/);
    Deno.writeTextFileSync(join(p.root, ".cache", "coro", "CURRENT"), "missing_1\n");
    for (const command of ["hold", "unhold", "send"]) {
      const result = await p.call([command], "work");
      assert.equal(result.code, 1);
      assert.match(result.err, /no session 'missing_1' on disk/);
    }
  }));

Deno.test("CLI phase scaffolds substitute slug and protect both existing files", () =>
  project(async (p) => {
    successful(await p.call(["new-phase", "test"]));
    const todo = join(p.root, ".cache", "TODO");
    for (const file of ["phase.md", "phase-kickoff.md"]) {
      const output = file === "phase.md" ? "phase-test.md" : "phase-test-kickoff.md";
      assert.equal(
        Deno.readTextFileSync(join(todo, output)),
        Deno.readTextFileSync(join(skill, "templates", file)).replaceAll("{slug}", "test"),
      );
    }
    Deno.writeTextFileSync(join(todo, "phase-test.md"), "custom");
    assert.equal((await p.call(["new-phase", "test"])).code, 1);
    assert.equal(Deno.readTextFileSync(join(todo, "phase-test.md")), "custom");
    successful(await p.call(["new-phase", "test", "--force"]));
    assert.notEqual(Deno.readTextFileSync(join(todo, "phase-test.md")), "custom");
  }));

Deno.test("CLI rejects invalid arguments before mutating state and supports subcommand help", () =>
  project(async (p) => {
    for (
      const args of [
        [],
        ["unknown"],
        ["create"],
        ["create", "a", "b"],
        ["new-phase"],
        ["use"],
        ["status", "a", "b"],
        ["list", "extra"],
        ["log", "x", "not-an-int"],
        ["send", "--bogus"],
      ]
    ) {
      const r = await p.call(args);
      assert.equal(r.code, 2, JSON.stringify({ args, ...r }));
    }
    for (
      const command of [
        "create",
        "send",
        "status",
        "turns",
        "log",
        "use",
        "pop",
        "list",
        "hold",
        "unhold",
        "new-phase",
      ]
    ) {
      const r = await p.call([command, "--help"]);
      successful(r);
      assert.match(r.out, /usage:/i);
    }
    const help = await p.call(["--help"]);
    for (
      const name of [
        "CORO_MODEL",
        "CORO_EFFORT",
        "CORO_PROJECT",
        "CORO_ADD_DIRS",
        "CORO_MAX_BUDGET_USD",
        "CORO_TOKEN_WARN",
        "CORO_COST_WARN",
      ]
    ) {
      assert(help.out.includes(name), name);
    }
    assert.equal((await p.call(["create", "already_123"])).code, 1);
  }));

Deno.test("CLI uses physical skill config through a symlink and preserves caller project", () =>
  project(async (p) => {
    const link = join(p.root, "linked skill");
    Deno.symlinkSync(skill, link);
    Deno.writeTextFileSync(join(p.root, "deno.json"), "invalid caller config");
    const child = new Deno.Command(join(link, "scripts", "coro"), {
      args: ["new-phase", "mounted"],
      cwd: p.root,
      env: { ...p.env, CORO_PROJECT: "" },
      clearEnv: true,
      stdout: "piped",
      stderr: "piped",
    });
    const r = await child.output();
    assert.equal(r.code, 0, decode(r.stderr));
    assert(Deno.statSync(join(p.root, ".cache", "TODO", "phase-mounted.md")).isFile);
  }));

Deno.test("CLI refuses a concurrent send and status observes the other process lock", () =>
  project(async (p) => {
    const dir = seed(p);
    const lock = join(dir, "lock");
    const code =
      'const f=Deno.openSync(Deno.args[0],{create:true,write:true});f.lockSync(true);console.log("locked");await new Response(Deno.stdin.readable).text();f.close();';
    const holder = new Deno.Command(Deno.execPath(), {
      args: ["eval", code, lock],
      stdin: "piped",
      stdout: "piped",
      stderr: "piped",
    }).spawn();
    const reader = holder.stdout.getReader();
    try {
      assert.equal(decode((await reader.read()).value!), "locked\n");
      const r = await p.call(["send"], "work");
      assert.equal(r.code, 1);
      assert.match(r.err, /another send is in flight/);
      assert.match((await p.call(["status"])).out, /sending: {2}yes/);
      assert.throws(() => Deno.statSync(join(dir, "turns", "001.jsonl")), Deno.errors.NotFound);
    } finally {
      reader.releaseLock();
      await holder.stdin.close();
      assert((await holder.status).success);
      await holder.output();
    }
    successful(await p.call(["send"], "after release"));
  }));

Deno.test("CLI flushes complete turn events before the child finishes", () =>
  project(async (p) => {
    const dir = seed(p);
    const gate = join(p.root, "release");
    const running = p.call(["send"], "work", { CORO_TEST_MODE: "pause", CORO_TEST_GATE: gate });
    let result;
    try {
      const deadline = Date.now() + 5000;
      let events: Json[] = [];
      while (Date.now() < deadline) {
        try {
          events = readLines(join(dir, "turns", "001.jsonl"));
        } catch (e) {
          if (!(e instanceof Deno.errors.NotFound)) throw e;
        }
        if (events.some((e) => e.type === "assistant")) break;
        await new Promise((resolve) => setTimeout(resolve, 20));
      }
      assert(events.some((e) => e.type === "assistant"), "assistant event was not flushed");
      assert(!events.some((e) => e.type === "result"), "fixture should still be waiting");
      assert.match((await p.call(["status"])).out, /sending: {2}yes/);
    } finally {
      Deno.writeTextFileSync(gate, "");
      result = await running;
    }
    successful(result);
    assert.equal(readLines(join(dir, "turns", "001.jsonl")).at(-1)?.type, "result");
  }));
