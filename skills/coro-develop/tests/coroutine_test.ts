import assert from "node:assert/strict";
const assertEquals: typeof assert.deepEqual = assert.deepEqual;
const assertThrows: typeof assert.throws = assert.throws;
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import {
  acquireSendLock,
  budgetExceeded,
  buildClaudeArgv,
  checkSendLock,
  clearHold,
  CliUsageError,
  CoroError,
  costWarnThreshold,
  currentList,
  currentPop,
  currentPush,
  extractContextWindow,
  extractMaxOutput,
  extractResult,
  extractSessionId,
  extractText,
  extractYield,
  findProjectRoot,
  formatCost,
  lastTurnNumber,
  listSlugs,
  main,
  makeSlug,
  nextTurnNumber,
  parseCommand,
  parseSlug,
  readHold,
  resolve,
  resolveSessionArg,
  resolveSlug,
  resultTokens,
  runClaude,
  saveSession,
  saveTurn,
  sessionTotalCost,
  skillRoot,
  SubprocessRunner,
  tokenWarnThreshold,
  writeHold,
} from "../scripts/coroutine.ts";

const temporaryDirectories: string[] = [];
function removeTemporary(path: string) {
  try {
    Deno.removeSync(path, { recursive: true });
  } catch (e) {
    if (!(e instanceof Deno.errors.NotFound)) throw e;
  }
}
function test(name: string, body: () => void | Promise<void>) {
  Deno.test(name, async () => {
    const keys = [
      "CORO_MODEL",
      "CORO_EFFORT",
      "CORO_PROJECT",
      "CORO_ADD_DIRS",
      "CORO_MAX_BUDGET_USD",
      "CORO_TOKEN_WARN",
      "CORO_TOKEN_WARN_RATIO",
      "CORO_COST_WARN",
      "CLAUDE_CODE_DISABLE_1M_CONTEXT",
      "API_TIMEOUT_MS",
      "BASH_MAX_TIMEOUT_MS",
    ];
    const saved = keys.map((key) => Deno.env.get(key));
    for (const key of keys) Deno.env.delete(key);
    try {
      await body();
    } finally {
      for (const path of temporaryDirectories.splice(0)) {
        removeTemporary(path);
      }
      keys.forEach((key, i) =>
        saved[i] === undefined ? Deno.env.delete(key) : Deno.env.set(key, saved[i]!)
      );
    }
  });
}

function fixture() {
  const p = Deno.makeTempDirSync();
  temporaryDirectories.push(p);
  Deno.mkdirSync(join(p, ".cache", "coro"), { recursive: true });
  return p;
}
test("model registry, argv, and YIELD extraction preserve protocol", () => {
  assertEquals(resolve("sonnet").effort, "high");
  assertEquals(resolve("haiku", "high").effort, null);
  assert(buildClaudeArgv(resolve("sonnet"), "id").includes("--session-id"));
  assertThrows(() => buildClaudeArgv(resolve("sonnet")), CoroError);
  assertEquals(extractYield("x\nYIELD: DONE | ok\nmore"), "YIELD: DONE | ok");
  assertEquals(
    extractText([{
      type: "assistant",
      message: { content: [{ type: "text", text: "a" }, { type: "text", text: "b" }] },
    }]),
    "ab",
  );
});
test("slug resolution, storage, CURRENT, hold, and cost are compatible", () => {
  const p = fixture();
  saveSession(p, "phase_100", "one", "sonnet");
  saveSession(p, "phase_200", "two", "sonnet");
  assertEquals(makeSlug("x", () => 123400), "x_123");
  assertEquals(parseSlug("a_b_2"), ["a_b", 2]);
  assertEquals(listSlugs(p), ["phase_100", "phase_200"]);
  assertThrows(() => resolveSlug(p, "phase"), CoroError);
  assertEquals(resolveSlug(p, "phase_100"), "phase_100");
  currentPush(p, "phase_100");
  currentPush(p, "phase_200");
  assertEquals(currentList(p), ["phase_100", "phase_200"]);
  assertEquals(resolveSessionArg(p), "phase_200");
  assertEquals(currentPop(p), "phase_200");
  writeHold(p, "phase_100", "wait");
  assertEquals(readHold(p, "phase_100"), [true, "wait"]);
  assertEquals(clearHold(p, "phase_100"), "wait");
  saveTurn(p, "phase_100", 0, [{ type: "result", total_cost_usd: 0.1 }]);
  saveTurn(p, "phase_100", 1, [{ type: "result", total_cost_usd: 0.2 }]);
  assertEquals(sessionTotalCost(p, "phase_100"), 0.30000000000000004);
});
test("exclusive advisory lock blocks and releases", () => {
  const p = fixture();
  saveSession(p, "x_1", "u", "sonnet");
  assertEquals(checkSendLock(p, "x_1"), false);
  const a = acquireSendLock(p, "x_1");
  try {
    assertEquals(checkSendLock(p, "x_1"), true);
    assertThrows(() => acquireSendLock(p, "x_1"), CoroError);
  } finally {
    a.close();
  }
  assertEquals(checkSendLock(p, "x_1"), false);
});
test("subprocess runner handles JSON, UTF-8, stdin, and stderr without blocking", async () => {
  const p = fixture();
  const runner = new SubprocessRunner();
  const code =
    'const d=await new Response(Deno.stdin.readable).text(); await Deno.stdout.write(new TextEncoder().encode("bad\\n"+JSON.stringify({stdin:d,text:"✓"})+"\\n")); await Deno.stderr.write(new Uint8Array(100000));';
  const got = [];
  for await (
    const e of runner.runStreamJson([Deno.execPath(), "eval", code], {
      cwd: p,
      env: Deno.env.toObject(),
      stdinPayload: "hello",
    })
  ) got.push(e);
  assertEquals(got, [{ stdin: "hello", text: "✓" }]);
});
test("result helpers, thresholds, and all yield forms", () => {
  const result = {
    type: "result",
    subtype: "error_max_budget_usd",
    usage: {
      input_tokens: 1,
      cache_read_input_tokens: 2,
      cache_creation_input_tokens: 3,
      output_tokens: 4,
    },
    modelUsage: { x: { contextWindow: 9, maxOutputTokens: 8 } },
  };
  assert.equal(budgetExceeded(result), true);
  assert.deepEqual(resultTokens(result), [1, 2, 3, 4]);
  assert.equal(extractContextWindow(result), 9);
  assert.equal(extractMaxOutput(result), 8);
  assert.equal(extractResult([{ type: "system" }, result]), result);
  assert.equal(extractSessionId([{ type: "system", session_id: "a" }]), "a");
  for (
    const text of [
      "YIELD: DONE | x",
      "yield: BLOCKED | x",
      "x\nYIELD: FAILED | x\nz",
      "YIELD: CHECK | x",
      "YIELD: RUNNING | x",
    ]
  ) {
    assert(
      String(extractYield(text)).startsWith("YIELD:") ||
        String(extractYield(text)).startsWith("yield:"),
    );
  }
  assert.equal(tokenWarnThreshold(resolve("sonnet")), 160000);
  assert.equal(costWarnThreshold(resolve("haiku")), 10);
});
test("turn numbering, empty/missing state and malformed name rejection", () => {
  const p = fixture();
  assert.equal(lastTurnNumber(p, "none_1"), -1);
  saveSession(p, "x_1", "u", "sonnet");
  assert.equal(nextTurnNumber(p, "x_1"), 0);
  saveTurn(p, "x_1", 0, []);
  assert.equal(nextTurnNumber(p, "x_1"), 1);
  assert.equal(lastTurnNumber(p, "x_1"), 0);
  assert.throws(() => resolveSessionArg(p, ""), CoroError);
  assert.throws(() => resolveSessionArg(p), CoroError);
});
test("CLI hold, unhold, and new-phase preserve persisted protocol", async () => {
  const p = fixture(), old = Deno.env.get("CORO_PROJECT");
  Deno.env.set("CORO_PROJECT", p);
  saveSession(p, "phase_1", "u", "sonnet");
  currentPush(p, "phase_1");
  try {
    await main(["hold", "phase", "wait", "review"]);
    assert.deepEqual(readHold(p, "phase_1"), [true, "wait review"]);
    await main(["unhold", "phase"]);
    await main(["new-phase", "demo"]);
    assert(Deno.statSync(join(p, ".cache", "TODO", "phase-demo.md")).isFile);
  } finally {
    if (old === undefined) Deno.env.delete("CORO_PROJECT");
    else Deno.env.set("CORO_PROJECT", old);
    Deno.removeSync(p, { recursive: true });
  }
});
test("missing project override reports CoroError", () => {
  const old = Deno.env.get("CORO_PROJECT");
  Deno.env.set("CORO_PROJECT", join(Deno.cwd(), "missing-coro-project"));
  try {
    assert.throws(() => findProjectRoot(), CoroError);
  } finally {
    if (old === undefined) Deno.env.delete("CORO_PROJECT");
    else Deno.env.set("CORO_PROJECT", old);
  }
});
test("model aliases, extended contexts, and effort fallbacks are deterministic", () => {
  for (
    const [input, id, effort] of [
      ["opus", "claude-opus-4-7", "xhigh"],
      ["best", "claude-opus-4-7", "xhigh"],
      ["sonnet", "claude-sonnet-4-6", "high"],
      ["haiku", "claude-haiku-4-5", null],
    ] as const
  ) {
    const r = resolve(input);
    assert.equal(r.spec?.id, id);
    assert.equal(r.effort, effort);
  }
  assert.equal(tokenWarnThreshold(resolve("opus[1m]")), 800000);
  assert.equal(resolve("unknown", "max").effort, "max");
  assert.equal(resolve("sonnet", "invalid").effort, "high");
});
for (
  const [id, names, defaultEffort, extendedContext] of [
    [
      "claude-opus-4-7",
      ["opus", "best", "claude-opus-4-7", "claude-opus-4-7-20260101"],
      "xhigh",
      1000000,
    ],
    [
      "claude-sonnet-4-6",
      ["sonnet", "claude-sonnet-4-6", "claude-sonnet-4-6-20260101"],
      "high",
      1000000,
    ],
    ["claude-haiku-4-5", ["haiku", "claude-haiku-4-5", "claude-haiku-4-5-20260101"], null, 200000],
  ] as const
) {
  for (const name of names) {
    for (const suffix of ["", "[1m]"]) {
      for (
        const requested of [
          undefined,
          "",
          "low",
          "medium",
          "high",
          "xhigh",
          "max",
          "invalid",
          " HIGH ",
        ]
      ) {
        test("model compatibility: " + name + suffix + " effort=" + String(requested), () => {
          const r = resolve(name + suffix, requested);
          const normalized = requested?.trim().toLowerCase();
          const expected = defaultEffort === null
            ? null
            : normalized && normalized !== "invalid"
            ? normalized
            : defaultEffort;
          assert.equal(r.claudeArg, name + suffix);
          assert.equal(r.spec?.id, id);
          assert.equal(r.extended, suffix !== "");
          assert.equal(r.effort, expected);
          assert.equal(tokenWarnThreshold(r), (suffix ? extendedContext : 200000) * 0.8);
          if (normalized === "invalid") assert.match(r.warnings.join("\n"), /invalid CORO_EFFORT/);
          else if (normalized && defaultEffort === null) {
            assert.match(r.warnings.join("\n"), /does not support/);
          } else if (normalized === "xhigh" && defaultEffort === "high") {
            assert.match(r.warnings.join("\n"), /downgrade/);
          } else assert.deepEqual(r.warnings, []);
        });
      }
    }
  }
}
test("generated slug CURRENT turn cost and YIELD invariants", () => {
  const p = fixture();
  try {
    for (let i = 0; i < 30; i++) {
      const name = `é_${i}_名`;
      const slug = makeSlug(name, () => 1700000000000 + i * 1000);
      assert.deepEqual(parseSlug(slug), [name, 1700000000 + i]);
      saveSession(p, slug, `u${i}`, "sonnet");
      currentPush(p, slug);
      saveTurn(p, slug, 0, [{ type: "result", total_cost_usd: i / 10 }]);
      assert.equal(nextTurnNumber(p, slug), 1);
    }
    for (let i = 29; i >= 0; i--) {
      const slug = makeSlug(`é_${i}_名`, () => 1700000000000 + i * 1000);
      assert.equal(currentPop(p), slug);
      assert.equal(resolveSlug(p, `é_${i}_名`), slug);
    }
    assert.equal(currentPop(p), null);
    assert.equal(listSlugs(p).length, 30);
    saveSession(p, "dup_1", "a", "sonnet");
    saveSession(p, "dup_2", "b", "sonnet");
    assert.throws(() => resolveSlug(p, "dup"), CoroError);
    assert.equal(sessionTotalCost(p, makeSlug("é_4_名", () => 1700000004000)), 0.4);
    for (
      const y of [" \n YIELD: DONE | x \n", "x\n\tYIELD: CHECK | z\n", "YIELD: FAILED | x\n\n"]
    ) assert(String(extractYield(y)).toUpperCase().startsWith("YIELD:"));
  } finally {
    Deno.removeSync(p, { recursive: true });
  }
});
test("runClaude injected runner captures exact transport and callback recovery", async () => {
  const p = fixture(), calls: unknown[] = [];
  const events = [{ type: "system", session_id: "s" }, {
    type: "assistant",
    message: { content: [{ type: "text", text: "ok" }] },
  }];
  const runner = {
    async *runStreamJson(argv: string[], options: unknown) {
      calls.push({ argv, options });
      yield events[0];
      yield events[1];
    },
  };
  try {
    const got = await runClaude(p, "payload", resolve("sonnet"), {
      sessionId: "id",
      runner,
      onEvent: () => {
        throw new Error("ignore");
      },
    });
    assert.deepEqual(got, events);
    const call = calls[0] as {
      argv: string[];
      options: { stdinPayload: string; env: Record<string, string> };
    };
    assert.deepEqual(call.argv, buildClaudeArgv(resolve("sonnet"), "id"));
    assert.equal(call.options.stdinPayload, "payload");
    assert.equal(call.options.env.API_TIMEOUT_MS, "1200000");
    assert.equal(call.options.env.BASH_MAX_TIMEOUT_MS, "1200000");
    assert.throws(() => buildClaudeArgv(resolve("sonnet"), undefined, undefined), CoroError);
    assert.throws(() => buildClaudeArgv(resolve("sonnet"), "a", "b"), CoroError);
  } finally {
    Deno.removeSync(p, { recursive: true });
  }
});

test("option parsing preserves flag order and explicit end-of-options", () => {
  assert.deepEqual(parseCommand(["new-phase", "--force", "phase"]).args, ["phase"]);
  assert.equal(parseCommand(["new-phase", "--force", "phase"]).force, true);
  assert.equal(parseCommand(["new-phase", "phase", "--force"]).force, true);
  assert.deepEqual(parseCommand(["new-phase", "--", "--force"]).args, ["--force"]);
  assert.equal(parseCommand(["new-phase", "--", "--force"]).force, false);
  assert.deepEqual(parseCommand(["hold", "worker", "--", "--help"]).args, ["worker", "--help"]);
  assert.deepEqual(parseCommand(["log", "worker", "+1_000"]).args, ["worker", "+1000"]);
  for (
    const args of [[], ["unknown", "--help"], ["send", "--bad"], ["create", "a", "b"], [
      "log",
      "x",
      "1.5",
    ]]
  ) {
    assert.throws(() => parseCommand(args), CliUsageError);
  }
});
test("skill root uses the sentinel and resolves nested sources", () => {
  const root = fixture();
  const script = join(root, "nested", "scripts", "test.ts");
  Deno.mkdirSync(join(root, "nested", "scripts"), { recursive: true });
  Deno.writeTextFileSync(script, "");
  assert.throws(() => skillRoot(pathToFileURL(script).href), /SKILL.md sentinel not found/);
  Deno.writeTextFileSync(join(root, "SKILL.md"), "# fixture");
  assert.equal(skillRoot(pathToFileURL(script).href), Deno.realPathSync(root));
});
test("cost diagnostics round values rather than truncating cents", () => {
  for (
    const [value, expected] of [
      [0.625, "0.62"],
      [0.375, "0.38"],
      [0.619, "0.62"],
      [0.615, "0.61"],
      [0.675, "0.68"],
      [1.999, "2.00"],
    ] as const
  ) {
    assert.equal(formatCost(value), expected);
  }
});
