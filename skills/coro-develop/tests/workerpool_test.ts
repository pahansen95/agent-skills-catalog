import assert from "node:assert/strict";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  atomicJson,
  checkAttempt,
  markUnknown,
  observeTask,
  readPool,
  reconcileTask,
  sealAttempt,
  snapshotAttempt,
} from "../scripts/pool.ts";
import { parseYield, readService, serviceCall, streamArgv } from "../scripts/transport.ts";
const launcher = fileURLToPath(new URL("../scripts/coro", import.meta.url));
const fixture = fileURLToPath(new URL("fixtures/stream.ts", import.meta.url));
const pause = () => new Promise((r) => setTimeout(r, 30));
async function until<T>(read: () => Promise<T> | T, ready: (v: T) => boolean): Promise<T> {
  const deadline = Date.now() + 12000;
  for (;;) {
    const value = await read();
    if (ready(value)) return value;
    if (Date.now() > deadline) throw new Error(`timed out: ${JSON.stringify(value)}`);
    await pause();
  }
}
async function project(
  run: (
    p: {
      root: string;
      call: (
        args: string[],
        content?: string,
      ) => Promise<{ code: number; out: string; err: string }>;
    },
  ) => Promise<void>,
  cancel = "normal",
) {
  const root = Deno.makeTempDirSync({ prefix: "coro-pool-" });
  const shim = join(root, "claude");
  Deno.writeTextFileSync(
    shim,
    '#!/bin/sh\nexec "$CORO_TEST_DENO" run --no-config --allow-env --allow-read --allow-write "$CORO_TEST_FIXTURE" "$@"\n',
  );
  Deno.chmodSync(shim, 0o755);
  const env = Deno.env.toObject();
  for (const key of Object.keys(env)) if (key.startsWith("CORO_")) delete env[key];
  Object.assign(env, {
    CORO_PROJECT: root,
    CORO_CLAUDE: shim,
    CORO_PERSISTENCE: "journal",
    CORO_TEST_DENO: Deno.execPath(),
    CORO_TEST_FIXTURE: fixture,
    CORO_TEST_CAPTURE: join(root, "calls"),
    CORO_TEST_MESSAGES: join(root, "messages"),
    CORO_TEST_CANCEL: cancel,
  });
  const call = async (args: string[], content = "") => {
    const child = new Deno.Command(launcher, {
      args,
      cwd: root,
      env,
      clearEnv: true,
      stdin: "piped",
      stdout: "piped",
      stderr: "piped",
    }).spawn();
    const output = child.output();
    const w = child.stdin.getWriter();
    await w.write(new TextEncoder().encode(content));
    await w.close();
    const r = await output;
    return {
      code: r.code,
      out: new TextDecoder().decode(r.stdout),
      err: new TextDecoder().decode(r.stderr),
    };
  };
  try {
    await run({ root, call });
  } finally {
    try {
      for (const entry of Deno.readDirSync(join(root, ".cache/coro"))) {
        if (!entry.isDirectory) continue;
        const dir = join(root, ".cache/coro", entry.name);
        try {
          if (readService(dir)) await serviceCall(dir, { op: "shutdown" });
        } catch { /* test may already have stopped service */ }
        await until(() => readService(dir), (e) => !e);
      }
    } finally {
      Deno.removeSync(root, { recursive: true });
    }
  }
}
const ok = (r: { code: number; out: string; err: string }) => {
  assert.equal(r.code, 0, r.err);
  return r.out;
};
Deno.test("coordinator frontend separates turns, tasks, holds and cancellation", () =>
  project(async ({ root, call }) => {
    const slug = ok(await call(["create", "probe"])).trim(), dir = join(root, ".cache/coro", slug);
    const status = () => serviceCall(dir, { op: "status" });
    await until(status, (s) => !s.busy);
    const meta = JSON.parse(Deno.readTextFileSync(join(dir, "meta")));
    assert.equal(meta.role, "coordinator");
    assert.equal(meta.profile.persistence, "journal");
    ok(await call(["send"], "start"));
    await until(status, (s) => !s.busy && s.tasks["workflow-1"]?.state === "running");
    ok(await call(["send"], "observe"));
    await until(status, (s) => !s.busy);
    assert.equal(Deno.readTextFileSync(join(root, "calls")).trim().split("\n").length, 1);
    ok(await call(["hold", slug, "review"]));
    assert.equal((await call(["send"], "forbidden")).code, 1);
    assert.equal((await status()).held, true);
    const cancelled = JSON.parse(ok(await call(["cancel"])));
    assert.equal(cancelled.confirmed, true);
    assert.equal(cancelled.tasks["workflow-1"].state, "cancelled");
    ok(await call(["unhold"]));
    ok(await call(["send"], "slow"));
    assert.equal((await status()).busy, true); // background result must not end this turn
    assert.equal(
      (await until(status, (s) => !!s.lastNotification)).lastNotification.result,
      "background",
    );
    assert.equal((await call(["send"], "overlap")).code, 1);
    await until(status, (s) => !s.busy);
    ok(await call(["send"], "bad-yield"));
    assert.match((await until(status, (s) => !s.busy)).protocolError, /canonical YIELD/);
    assert.equal((await call(["persistence", slug, "native"])).code, 1);
    ok(await call(["shutdown"]));
    await until(() => readService(dir), (s) => !s);
    ok(await call(["persistence", slug, "native"]));
    ok(await call(["persistence", slug, "journal"]));
    ok(await call(["unhold"]));
    ok(await call(["send"], "rehydrate"));
    await until(status, (s) => !s.busy);
    const messages = Deno.readTextFileSync(join(root, "messages")).trim().split("\n").map((v) =>
      JSON.parse(v)
    );
    assert.match(messages.at(-1).content, /Restoring this logical coroutine/);
    assert(!messages.at(-1).content.includes('"instruction":"forbidden"'));
    assert.match(messages.at(-1).content, /rehydrate$/);
  }));
Deno.test("lost termination is unknown until explicitly reconciled", () =>
  project(async ({ root, call }) => {
    const slug = ok(await call(["create", "lost"])).trim(), dir = join(root, ".cache/coro", slug);
    const status = () => serviceCall(dir, { op: "status" });
    await until(status, (s) => !s.busy);
    ok(await call(["send"], "start"));
    await until(status, (s) => !s.busy);
    const cancelled = JSON.parse(ok(await call(["cancel"])));
    assert.equal(cancelled.confirmed, false);
    ok(await call(["unhold"]));
    ok(await call(["send"], "crash"));
    await until(status, (s) => !s.connected);
    assert.equal(readPool(dir).tasks["workflow-1"].state, "unknown");
    assert.equal((await call(["send"], "retry")).code, 1);
    assert.equal(
      (await call(["reconcile", slug, "workflow-1", "cancelled", "fixture stopped"])).code,
      1,
    );
    ok(await call(["shutdown"]));
    await until(() => readService(dir), (s) => !s);
    ok(await call(["unhold"]));
    assert.equal((await call(["send"], "retry")).code, 1);
    ok(
      await call([
        "reconcile",
        slug,
        "workflow-1",
        "cancelled",
        "fixture process exited; it has no subprocesses",
      ]),
    );
    ok(await call(["send"], "retry"));
    await until(status, (s) => !s.busy);
  }, "missing"));
Deno.test("attempt evidence remains immutable and detects changed dependencies", async () => {
  const root = Deno.makeTempDirSync();
  try {
    const request = join(root, "request.md"),
      input = join(root, "input"),
      output = join(root, "output");
    Deno.writeTextFileSync(request, "approved");
    Deno.writeTextFileSync(input, "source v1");
    Deno.writeTextFileSync(output, "draft");
    await snapshotAttempt(root, { id: "a1", request, inputs: [input], outputs: [output] });
    assert.equal((await checkAttempt(root, "a1")).unchanged, false);
    await sealAttempt(root, "a1", { check: "reviewed draft", accepted: false });
    assert.equal((await checkAttempt(root, "a1")).unchanged, true);
    await assert.rejects(() => snapshotAttempt(root, { id: "a1", request }));
    await assert.rejects(() => sealAttempt(root, "a1", {}));
    Deno.writeTextFileSync(input, "source v2");
    assert.deepEqual((await checkAttempt(root, "a1")).changes, [input]);
    Deno.removeSync(output);
    assert.equal((await checkAttempt(root, "a1")).changes.length, 2);
    await assert.rejects(() => snapshotAttempt(root, { id: "../escape", request }));
    const pool = { tasks: {} };
    observeTask(pool, { type: "system", subtype: "task_started", task_id: "a" });
    markUnknown(pool);
    atomicJson(join(root, "pool.json"), pool);
    assert.throws(() => reconcileTask(root, "a", "cancelled", ""));
    reconcileTask(root, "a", "cancelled", "termination observed");
    assert.equal(
      observeTask(readPool(root), { type: "system", subtype: "task_progress", task_id: "a" }),
      false,
    );
  } finally {
    Deno.removeSync(root, { recursive: true });
  }
});
Deno.test("native/journal transport and canonical response boundaries", () => {
  const profile = {
    executable: "claude",
    model: "fixture-model",
    effort: "high",
    persistence: "native" as const,
  };
  assert(streamArgv(profile, "id", true).includes("--resume"));
  const journal = streamArgv({ ...profile, persistence: "journal" }, "id", true);
  assert(!journal.includes("--resume"));
  assert(journal.includes("--no-session-persistence"));
  assert(!journal.includes("--dangerously-skip-permissions"));
  assert.equal(parseYield("YIELD: DONE | valid"), "YIELD: DONE | valid");
  assert.equal(parseYield("YIELD: DONE | early\nextra"), undefined);
  assert.equal(parseYield("YIELD: DONE | early\nYIELD: CHECK | duplicate"), undefined);
});

Deno.test("frontier models use verified default limits and every supported effort", async () => {
  const { resolve, resolvedContextWindow, tokenWarnThreshold, connectionProfile } = await import(
    "../scripts/coroutine.ts"
  );
  for (
    const [alias, id] of [["fable", "claude-fable-5-1"], ["best", "claude-fable-5-1"], [
      "opus",
      "claude-opus-5",
    ], ["sonnet", "claude-sonnet-5"]]
  ) {
    assert.equal(resolve(alias).spec?.id, id);
    for (const name of [alias, id, id + "[1m]"]) {
      assert.equal(resolve(name).effort, "high");
      assert.equal(resolvedContextWindow(resolve(name)), 1000000);
      assert.equal(resolve(name).spec?.maxOutput, 128000);
      assert.equal(tokenWarnThreshold(resolve(name)), 800000);
      for (const effort of ["low", "medium", "high", "xhigh", "max"]) {
        assert.equal(resolve(name, effort).effort, effort);
        assert.deepEqual(resolve(name, effort).warnings, []);
      }
    }
  }
  for (const id of ["claude-opus-4-7", "claude-sonnet-4-6"]) {
    assert.equal(resolve(id).spec, undefined);
    assert.match(resolve(id).warnings[0], /unknown model/);
  }
  const prior = Deno.env.get("CORO_MODEL");
  try {
    Deno.env.set("CORO_MODEL", "fable");
    assert.equal(connectionProfile().model, "claude-fable-5-1");
  } finally {
    if (prior === undefined) Deno.env.delete("CORO_MODEL");
    else Deno.env.set("CORO_MODEL", prior);
  }
});

Deno.test("a crashed frontend cannot replace a surviving Claude process", () =>
  project(async ({ root, call }) => {
    const slug = ok(await call(["create", "orphan"])).trim(), dir = join(root, ".cache/coro", slug);
    await until(() => serviceCall(dir, { op: "status" }), (s) => !s.busy);
    ok(await call(["send"], "linger"));
    const state = await until(() => serviceCall(dir, { op: "status" }), (s) => !s.busy);
    Deno.kill(state.pid, "SIGKILL");
    const alive = (pid: number) => {
      try {
        Deno.kill(pid, 0);
        return true;
      } catch (e) {
        if (e instanceof Deno.errors.NotFound) return false;
        throw e;
      }
    };
    try {
      await until(() => alive(state.pid), (v) => !v);
      assert(alive(state.childPid));
      const retry = await call(["send"], "replacement");
      assert.equal(retry.code, 1);
      assert.match(retry.err, /may still be active/);
    } finally {
      try {
        Deno.kill(state.childPid, "SIGTERM");
      } catch (e) {
        assert(e instanceof Deno.errors.NotFound, String(e));
      }
      await until(() => alive(state.childPid), (v) => !v);
      Deno.removeSync(join(dir, "service.json"));
    }
    ok(await call(["send"], "restored"));
    await until(() => serviceCall(dir, { op: "status" }), (s) => !s.busy);
  }));
