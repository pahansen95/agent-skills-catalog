#!/usr/bin/env -S deno run
/** Stateful Claude session manager.  The files it writes are deliberately
 * compatible with the former Python implementation. */
import { dirname, join } from "node:path";

export class CoroError extends Error {}
type Event = Record<string, unknown>;
const DEFAULT_MODEL = "sonnet";
const specs = [
  {
    id: "claude-opus-4-7",
    aliases: ["opus", "best"],
    context: 200000,
    extended: 1000000,
    maxOutput: 128000,
    efforts: ["low", "medium", "high", "xhigh", "max"],
    defaultEffort: "xhigh",
    cost: 50,
  },
  {
    id: "claude-sonnet-4-6",
    aliases: ["sonnet"],
    context: 200000,
    extended: 1000000,
    maxOutput: 64000,
    efforts: ["low", "medium", "high", "max"],
    defaultEffort: "high",
    cost: 25,
  },
  {
    id: "claude-haiku-4-5",
    aliases: ["haiku"],
    context: 200000,
    extended: null,
    maxOutput: 64000,
    efforts: [],
    defaultEffort: null,
    cost: 10,
  },
] as const;
type Spec = typeof specs[number];
export type ResolvedModel = {
  claudeArg: string;
  spec: Spec | undefined;
  extended: boolean;
  effort: string | null;
  warnings: string[];
};
const env = (name: string, fallback = "") => Deno.env.get(name)?.trim() || fallback;
export function resolve(
  input: string,
  effortInput?: string | null,
): ResolvedModel {
  const extended = input.endsWith("[1m]"),
    base = extended ? input.slice(0, -4) : input;
  const spec = specs.find((s) =>
    s.id === base || (s.aliases as readonly string[]).includes(base) ||
    base.includes(s.id)
  );
  const warnings: string[] = [];
  if (!spec) {
    warnings.push(
      `unknown model '${input}'; passing through to claude (warnings may be inaccurate)`,
    );
  }
  if (extended && env("CLAUDE_CODE_DISABLE_1M_CONTEXT") === "1") {
    warnings.push(
      "CLAUDE_CODE_DISABLE_1M_CONTEXT=1 in env; [1m] suffix will fail at claude",
    );
  }
  const requested = (effortInput || "").trim().toLowerCase();
  const valid = ["low", "medium", "high", "xhigh", "max"];
  let effort: string | null = null;
  if (requested) {
    if (!valid.includes(requested)) {
      warnings.push(`invalid CORO_EFFORT '${effortInput}'; using spec default`);
    } else if (!spec) effort = requested;
    else if (!spec.efforts.length) {
      warnings.push(
        `${spec.id} does not support --effort; dropping '${requested}'`,
      );
    } else {
      effort = requested;
      if (!spec.efforts.includes(requested as never)) {
        warnings.push(
          `${spec.id} does not support effort '${requested}' (supported: ${
            [...spec.efforts].sort().join(", ")
          }); claude will downgrade silently`,
        );
      }
    }
  }
  if (!requested || !valid.includes(requested)) {
    effort ??= spec?.defaultEffort ?? null;
  }
  return { claudeArg: input, spec, extended, effort, warnings };
}
export const resolvedContextWindow = (r: ResolvedModel) =>
  r.spec ? (r.extended && r.spec.extended || r.spec.context) : 200000;
export const tokenWarnThreshold = (r: ResolvedModel, context?: number) =>
  env("CORO_TOKEN_WARN") !== "" ? Number(env("CORO_TOKEN_WARN")) : Math.trunc(
    (context ?? resolvedContextWindow(r)) *
      Number(env("CORO_TOKEN_WARN_RATIO", "0.80")),
  );
export const costWarnThreshold = (r: ResolvedModel) =>
  env("CORO_COST_WARN") !== "" ? Number(env("CORO_COST_WARN")) : r.spec?.cost || 25;
export const coroDir = (root: string) => join(root, ".cache", "coro");
export const slugDir = (r: string, s: string) => join(coroDir(r), s);
export const sessionFile = (r: string, s: string) => join(slugDir(r, s), "uuid");
export const metaFile = (r: string, s: string) => join(slugDir(r, s), "meta");
export const sendLockPath = (r: string, s: string) => join(slugDir(r, s), "lock");
export const holdPath = (r: string, s: string) => join(slugDir(r, s), "hold");
export const turnsDir = (r: string, s: string) => join(slugDir(r, s), "turns");
export const turnLogFile = (r: string, s: string, t: number) =>
  join(turnsDir(r, s), `${String(t).padStart(3, "0")}.jsonl`);
export const currentPath = (r: string) => join(coroDir(r), "CURRENT");
const exists = (p: string) => {
  try {
    Deno.statSync(p);
    return true;
  } catch {
    return false;
  }
};
const text = (p: string) => Deno.readTextFileSync(p);
const write = (p: string, v: string) => {
  Deno.mkdirSync(dirname(p), { recursive: true });
  Deno.writeTextFileSync(p, v);
};
export const makeSlug = (name: string, now = Date.now) => `${name}_${Math.trunc(now() / 1000)}`;
export const parseSlug = (s: string) => {
  const m = /^(.+)_(\d+)$/.exec(s);
  return m ? [m[1], Number(m[2])] as [string, number] : null;
};
export function listSlugs(root: string) {
  if (!exists(coroDir(root))) return [];
  return [...Deno.readDirSync(coroDir(root))].filter((e) =>
    e.isDirectory && exists(sessionFile(root, e.name))
  ).map((e) => e.name).sort();
}
export function resolveSlug(root: string, arg: string) {
  if (exists(sessionFile(root, arg))) return arg;
  const ms = listSlugs(root).filter((s) => parseSlug(s)?.[0] === arg);
  if (!ms.length) {
    die(
      `no session matches '${arg}' — run 'coro list' or 'coro create ${arg}'`,
    );
  }
  if (ms.length > 1) {
    die(
      `'${arg}' is ambiguous — matches ${ms.length} sessions:\n  ${
        ms.join("\n  ")
      }\nspecify the full slug to disambiguate`,
    );
  }
  return ms[0];
}
export const currentList = (r: string) =>
  exists(currentPath(r)) ? text(currentPath(r)).split(/\r?\n/).filter((line) => line.trim()) : [];
export const currentTop = (r: string) => currentList(r).at(-1) ?? null;
export const currentPush = (r: string, s: string) =>
  write(currentPath(r), [...currentList(r), s].join("\n") + "\n");
export function currentPop(r: string) {
  const a = currentList(r);
  const x = a.pop();
  if (x !== undefined) {
    write(currentPath(r), a.length ? a.join("\n") + "\n" : "");
  }
  return x ?? null;
}
export function resolveSessionArg(r: string, arg?: string | null): string {
  if (arg !== undefined && arg !== null) return resolveSlug(r, arg);
  const s = currentTop(r);
  if (!s) {
    die(
      "no session specified and CURRENT stack is empty; run 'coro use <name-or-slug>' first",
    );
  }
  return s!;
}
export const loadSession = (r: string, s: string) => {
  const p = sessionFile(r, s);
  if (!exists(p)) die(`no session '${s}' on disk`);
  return text(p).trim();
};
export const loadMeta = (r: string, s: string): Record<string, unknown> =>
  exists(metaFile(r, s)) ? JSON.parse(text(metaFile(r, s))) : {};
export const saveSession = (
  r: string,
  s: string,
  id: string,
  model: string,
) => {
  write(sessionFile(r, s), id + "\n");
  write(metaFile(r, s), JSON.stringify({ model }) + "\n");
};
const logs = (r: string, s: string) =>
  exists(turnsDir(r, s))
    ? [...Deno.readDirSync(turnsDir(r, s))].filter((x) => x.isFile && x.name.endsWith(".jsonl"))
      .map((x) => x.name).sort()
    : [];
export const nextTurnNumber = (r: string, s: string) => {
  Deno.mkdirSync(turnsDir(r, s), { recursive: true });
  const a = logs(r, s);
  return a.length ? Number(a.at(-1)!.slice(0, -6)) + 1 : 0;
};
export const lastTurnNumber = (r: string, s: string) => {
  const a = logs(r, s);
  return a.length ? Number(a.at(-1)!.slice(0, -6)) : -1;
};
export const saveTurn = (r: string, s: string, t: number, ev: Event[]) =>
  write(
    turnLogFile(r, s, t),
    ev.map((event) => JSON.stringify(event)).join("\n") +
      (ev.length ? "\n" : ""),
  );
export function writeHold(r: string, s: string, reason: string) {
  write(holdPath(r, s), `${reason}\n${new Date().toISOString()}\n`);
}
export function readHold(r: string, s: string): [boolean, string] {
  if (!exists(holdPath(r, s))) return [false, ""];
  return [
    true,
    text(holdPath(r, s)).split(/\r?\n/)[0].trim() ? text(holdPath(r, s)).split(/\r?\n/)[0] : "",
  ];
}
export function clearHold(r: string, s: string) {
  if (!exists(holdPath(r, s))) return null;
  const v = readHold(r, s)[1];
  Deno.removeSync(holdPath(r, s));
  return v;
}
export function acquireSendLock(r: string, s: string) {
  Deno.mkdirSync(dirname(sendLockPath(r, s)), { recursive: true });
  const f = Deno.openSync(sendLockPath(r, s), { create: true, write: true });
  try {
    if (!f.tryLockSync(true)) die(`another send is in flight for session '${s}'`);
    return f;
  } catch (e) {
    f.close();
    throw e;
  }
}
export function checkSendLock(r: string, s: string) {
  if (!exists(sendLockPath(r, s))) return false;
  const f = Deno.openSync(sendLockPath(r, s), { read: true });
  try {
    return !f.tryLockSync(false);
  } finally {
    f.close();
  }
}
export const makePayload = (content: string) =>
  JSON.stringify({ type: "user", message: { role: "user", content } });
export const extractSessionId = (e: Event[]) =>
  e.find((x) => x.type === "system")?.session_id as string | undefined;
export const extractResult = (e: Event[]) => e.find((x) => x.type === "result");
export const extractText = (e: Event[]) =>
  e.filter((x) => x.type === "assistant").flatMap((x) =>
    ((x.message as Record<string, unknown>)?.content || []) as Event[]
  ).filter((x) => x.type === "text").map((x) => String(x.text ?? "")).join("");
export const extractYield = (v: string) =>
  v.trim().split(/\r?\n/).reverse().map((x) => x.trim()).find((x) =>
    x.toUpperCase().startsWith("YIELD:")
  );
export const budgetExceeded = (r: Event | undefined) => r?.subtype === "error_max_budget_usd";
export function resultTokens(r: Event): [number, number, number, number] {
  const u = (r.usage ?? {}) as Event;
  return [
    Number(u.input_tokens ?? 0),
    Number(u.cache_read_input_tokens ?? 0),
    Number(u.cache_creation_input_tokens ?? 0),
    Number(u.output_tokens ?? 0),
  ];
}
export function extractContextWindow(r: Event): number | undefined {
  for (const v of Object.values((r.modelUsage ?? {}) as Record<string, Event>)) {
    if (v.contextWindow) return Number(v.contextWindow);
  }
}
export function extractMaxOutput(r: Event): number | undefined {
  for (const v of Object.values((r.modelUsage ?? {}) as Record<string, Event>)) {
    if (v.maxOutputTokens) return Number(v.maxOutputTokens);
  }
}
const flags = (
  r: ResolvedModel,
) => [
  "--output-format",
  "stream-json",
  "--input-format",
  "stream-json",
  "--verbose",
  "--dangerously-skip-permissions",
  ...(r.effort ? ["--effort", r.effort] : []),
  ...env("CORO_ADD_DIRS").split(":").flatMap((d) => d.trim() ? ["--add-dir", d.trim()] : []),
];
export function buildClaudeArgv(
  r: ResolvedModel,
  sessionId?: string,
  resume?: string,
  maxBudget?: string,
) {
  if ((!sessionId) == (!resume)) {
    die("build_claude_argv requires exactly one of session_id or resume_uuid");
  }
  return [
    "claude",
    "--print",
    "--model",
    r.claudeArg,
    ...flags(r),
    ...(sessionId ? ["--session-id", sessionId] : ["--resume", resume!]),
    ...(maxBudget ? ["--max-budget-usd", maxBudget] : []),
  ];
}
export interface ProcessRunner {
  runStreamJson(
    argv: string[],
    options: { cwd: string; env: Record<string, string>; stdinPayload: string },
  ): AsyncIterable<Event>;
}
export class SubprocessRunner implements ProcessRunner {
  async *runStreamJson(
    argv: string[],
    o: { cwd: string; env: Record<string, string>; stdinPayload: string },
  ) {
    const p = new Deno.Command(argv[0], {
      args: argv.slice(1),
      cwd: o.cwd,
      env: o.env,
      clearEnv: true,
      stdin: "piped",
      stdout: "piped",
      stderr: "piped",
    }).spawn();
    const feed = (async () => {
      const w = p.stdin.getWriter();
      await w.write(new TextEncoder().encode(o.stdinPayload));
      await w.close();
    })().catch(() => {/* child may have exited before accepting stdin */});
    const stderr = (async () => {
      const reader = p.stderr.getReader(), chunks: Uint8Array[] = [];
      let size = 0;
      try {
        for (;;) {
          const item = await reader.read();
          if (item.done) break;
          if (size < 500) {
            const part = item.value.slice(0, 500 - size);
            chunks.push(part);
            size += part.length;
          }
        }
      } finally {
        reader.releaseLock();
      }
      const output = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) {
        output.set(chunk, offset);
        offset += chunk.length;
      }
      return new TextDecoder().decode(output);
    })();
    const reader = p.stdout.pipeThrough(new TextDecoderStream()).getReader();
    let buf = "";
    let completed = false;
    try {
      for (;;) {
        const q = await reader.read();
        if (q.done) break;
        buf += q.value;
        let i;
        while ((i = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, i).trim();
          buf = buf.slice(i + 1);
          try {
            if (line) yield JSON.parse(line);
          } catch { /* malformed stream line */ }
        }
      }
      if (buf.trim()) {
        try {
          yield JSON.parse(buf.trim());
        } catch { /* malformed trailing stream line */ }
      }
      completed = true;
    } finally {
      if (!completed) {
        try {
          p.kill("SIGTERM");
        } catch { /* child already exited */ }
      }
      try {
        await reader.cancel();
      } catch { /* reader already completed */ }
      reader.releaseLock();
      await feed;
      const status = await p.status;
      const err = await stderr;
      if (!status.success && err) {
        warn(`claude exited with code ${status.code}: ${err.trim()}`);
      }
    }
  }
}
export async function runClaude(
  root: string,
  payload: string,
  r: ResolvedModel,
  opts: {
    sessionId?: string;
    resume?: string;
    onEvent?: (e: Event) => void;
    runner?: ProcessRunner;
  } = {},
) {
  const argv = buildClaudeArgv(
    r,
    opts.sessionId,
    opts.resume,
    env("CORO_MAX_BUDGET_USD") || undefined,
  );
  const childEnv = {
    ...Deno.env.toObject(),
    API_TIMEOUT_MS: Deno.env.get("API_TIMEOUT_MS") ?? "1200000",
    BASH_MAX_TIMEOUT_MS: Deno.env.get("BASH_MAX_TIMEOUT_MS") ?? "1200000",
  };
  const events: Event[] = [];
  for await (
    const e of (opts.runner ?? new SubprocessRunner()).runStreamJson(argv, {
      cwd: root,
      env: childEnv,
      stdinPayload: payload,
    })
  ) {
    events.push(e);
    try {
      opts.onEvent?.(e);
    } catch (x) {
      warn(`on_event callback raised: ${x}`);
    }
  }
  return events;
}
const warn = (s: string) => console.error(s);
const die = (s: string): never => {
  throw new CoroError(s);
};
export function findProjectRoot() {
  const override = env("CORO_PROJECT");
  if (override) {
    if (!exists(override)) die(`CORO_PROJECT path does not exist: ${override}`);
    const p = Deno.realPathSync(override);
    return p;
  }
  let p = Deno.cwd();
  for (;;) {
    if (exists(coroDir(p))) return p;
    const q = dirname(p);
    if (q === p) return Deno.cwd();
    p = q;
  }
}
export function skillRoot(source = import.meta.url): string {
  let directory = dirname(Deno.realPathSync(new URL(source)));
  for (;;) {
    if (exists(join(directory, "SKILL.md"))) return directory;
    const parent = dirname(directory);
    if (parent === directory) {
      die("SKILL.md sentinel not found — coroutine.ts is running outside a skill directory");
    }
    directory = parent;
  }
}
function preamble() {
  const path = join(skillRoot(), "role", "worker.md");
  if (!exists(path)) die(`role/worker.md not found at ${path}`);
  return `/salience on\n\n${
    text(path).trim()
  }\n\nAcknowledge this role and wait for your first instruction.`;
}
function streamWriter(file: Deno.FsFile, visible = true) {
  return (e: Event) => {
    writeAll(file, new TextEncoder().encode(JSON.stringify(e) + "\n"));
    if (visible && e.type === "assistant") {
      for (
        const b of (((e.message as Record<string, unknown>)?.content ||
          []) as Event[])
      ) {
        if (b.type === "text") {
          writeAll(Deno.stdout, new TextEncoder().encode(String(b.text ?? "")));
        } else if (b.type === "tool_use") {
          console.error(
            `[coroutine] tool_use: ${b.name ?? "?"}(${
              Object.keys((b.input ?? {}) as Event).join(", ")
            })`,
          );
        }
      }
    } else if (visible && e.type === "user") {
      for (const b of (((e.message as Event)?.content ?? []) as Event[])) {
        if (b.type === "tool_result") {
          console.error(`[coroutine] tool_result: ${String(b.tool_use_id ?? "").slice(0, 12)}`);
        }
      }
    }
  };
}
function writeAll(file: { writeSync(bytes: Uint8Array): number }, bytes: Uint8Array) {
  let offset = 0;
  while (offset < bytes.length) offset += file.writeSync(bytes.subarray(offset));
}
async function create(root: string, name: string) {
  if (parseSlug(name)) {
    die(
      `refusing to create session with slug-shaped name '${name}' — pick a name without a trailing _<digits>`,
    );
  }
  const slug = makeSlug(name);
  if (exists(slugDir(root, slug))) {
    die(`slug '${slug}' already exists — wait a second and retry`);
  }
  const model = env("CORO_MODEL", DEFAULT_MODEL),
    r = resolve(model, env("CORO_EFFORT"));
  r.warnings.forEach(warn);
  const role = preamble();
  const id = crypto.randomUUID();
  saveSession(root, slug, id, model);
  currentPush(root, slug);
  console.error(
    `[coroutine] creating session slug=${slug} (model=${model}${
      r.effort ? " effort=" + r.effort : ""
    }) id=${id.slice(0, 8)}..`,
  );
  const turn = nextTurnNumber(root, slug),
    file = Deno.openSync(turnLogFile(root, slug, turn), {
      create: true,
      write: true,
    });
  let events;
  try {
    events = await runClaude(root, makePayload(role), r, {
      sessionId: id,
      onEvent: streamWriter(file, false),
    });
  } finally {
    file.close();
  }
  const reported = extractSessionId(events!);
  if (reported && reported !== id) {
    warn(
      `warning: claude reported session_id ${reported.slice(0, 8)}.. but we assigned ${
        id.slice(0, 8)
      }..`,
    );
  }
  const result = extractResult(events!);
  if (result?.is_error) {
    for (
      const p of [
        sessionFile(root, slug),
        metaFile(root, slug),
        holdPath(root, slug),
        sendLockPath(root, slug),
      ]
    ) {
      try {
        Deno.removeSync(p);
      } catch { /* bookkeeping may be absent */ }
    }
    if (currentTop(root) === slug) currentPop(root);
    die(
      budgetExceeded(result)
        ? `session creation aborted: budget of $${env("CORO_MAX_BUDGET_USD")} exceeded (spent $${
          Number(result.total_cost_usd ?? 0).toFixed(4)
        })`
        : `session creation failed: ${String(result.result ?? "unknown error")}`,
    );
  }
  console.error(
    `[coroutine] session=${id} turn=${turn} cost=$${
      Number(result?.total_cost_usd ?? 0).toFixed(4)
    }`,
  );
  console.error(`[coroutine] ${extractYield(extractText(events!)) ?? "(acknowledged)"}`);
  console.log(slug);
  if (!Deno.stdin.isTerminal()) {
    warn(
      "warning: 'coro create <name> < file' is deprecated; use 'coro send <name> < file' for turn 1",
    );
    const extra = (await new Response(Deno.stdin.readable).text()).trim();
    if (extra) {
      const inlineTurn = nextTurnNumber(root, slug);
      console.error(`[coroutine] sending initial content turn=${inlineTurn}...`);
      const inline = Deno.openSync(turnLogFile(root, slug, inlineTurn), {
        create: true,
        write: true,
      });
      let inlineEvents: Event[];
      try {
        inlineEvents = await runClaude(root, makePayload(extra), r, {
          resume: id,
          onEvent: streamWriter(inline),
        });
      } finally {
        inline.close();
      }
      const inlineResult = extractResult(inlineEvents!),
        inlineSignal = extractYield(extractText(inlineEvents!));
      console.error(
        `\n[coroutine] turn=${inlineTurn} cost=$${
          Number(inlineResult?.total_cost_usd ?? 0).toFixed(4)
        }`,
      );
      if (budgetExceeded(inlineResult)) {
        warn(
          `warning: turn exceeded CORO_MAX_BUDGET_USD=$${env("CORO_MAX_BUDGET_USD")} (spent $${
            Number(inlineResult?.total_cost_usd ?? 0).toFixed(4)
          }); session remains usable`,
        );
      }
      if (inlineSignal) console.error(`[coroutine] ${inlineSignal}`);
      else warn(`warning: turn ${inlineTurn} has no YIELD line; protocol violation`);
    }
  }
}
async function send(root: string, arg?: string) {
  const slug = resolveSessionArg(root, arg),
    id = loadSession(root, slug),
    meta = loadMeta(root, slug),
    model = String(meta.model ?? env("CORO_MODEL", DEFAULT_MODEL)),
    r = resolve(model, env("CORO_EFFORT"));
  r.warnings.forEach(warn);
  const content = (await new Response(Deno.stdin.readable).text()).trim();
  if (!content) die("stdin is empty");
  const priorHold = clearHold(root, slug);
  if (priorHold !== null) {
    console.error(
      `note: cleared hold on session '${slug}'${priorHold ? ` (reason: ${priorHold})` : ""}`,
    );
  }
  const lock = acquireSendLock(root, slug);
  try {
    console.error(
      `[coroutine] resuming ${slug} turn=${nextTurnNumber(root, slug)} model=${model}${
        r.effort ? " effort=" + r.effort : ""
      }...`,
    );
    const turn = nextTurnNumber(root, slug),
      file = Deno.openSync(turnLogFile(root, slug, turn), {
        create: true,
        write: true,
      });
    let ev;
    try {
      ev = await runClaude(root, makePayload(content), r, {
        resume: id,
        onEvent: streamWriter(file),
      });
    } finally {
      file.close();
    }
    const signal = extractYield(extractText(ev!));
    console.error(
      `\n[coroutine] turn=${turn} cost=$${
        Number(extractResult(ev!)?.total_cost_usd ?? 0).toFixed(4)
      }`,
    );
    if (budgetExceeded(extractResult(ev!))) {
      warn(
        `warning: turn exceeded CORO_MAX_BUDGET_USD=$${env("CORO_MAX_BUDGET_USD")} (spent $${
          Number(extractResult(ev!)?.total_cost_usd ?? 0).toFixed(4)
        }); session remains usable — raise cap or continue smaller`,
      );
    }
    if (signal) console.error(`[coroutine] ${signal}`);
    else warn(`warning: turn ${turn} has no YIELD line; protocol violation`);
  } finally {
    lock.close();
  }
}
function status(root: string, arg?: string) {
  const s = resolveSessionArg(root, arg),
    m = loadMeta(root, s),
    turn = lastTurnNumber(root, s);
  if (turn < 0) die(`no turns found for session '${s}'`);
  const ev = text(turnLogFile(root, s, turn)).split(/\r?\n/).filter(Boolean)
      .map((line) => JSON.parse(line)),
    result = extractResult(ev),
    body = extractText(ev);
  let signal = extractYield(body);
  let tokens = "-", totalContext = 0, runtimeMax: number | undefined;
  if (result) {
    const [input, read, creation, output] = resultTokens(result);
    totalContext = input + read + creation;
    runtimeMax = extractMaxOutput(result);
    tokens = `${totalContext} in / ${output} out${
      runtimeMax ? ` (cap ${runtimeMax})` : ""
    }  (last turn)`;
  }
  if (signal?.split("|")[0].replace("YIELD:", "").trim().toUpperCase() === "USER_HOLD") {
    warn(
      "warning: legacy USER_HOLD status observed; this signal is deprecated. Use 'coro hold' instead.",
    );
    signal = `YIELD: BLOCKED |${
      signal.includes("|") ? signal.split("|", 2)[1] : ""
    } (legacy USER_HOLD)`;
  }
  const hold = readHold(root, s);
  const totalCost = sessionTotalCost(root, s);
  const resolved = resolve(String(m.model ?? DEFAULT_MODEL));
  const yieldDisplay = signal ??
    `(no YIELD signal in turn ${turn}) last: ${(body.trim().split(/\r?\n/).at(-1) ||
      "(no output)")}`;
  console.log(
    `session:  ${s}\nmodel:    ${m.model ?? DEFAULT_MODEL}\nsending:  ${
      checkSendLock(root, s) ? "yes" : "no"
    }\nhold:     ${
      hold[0] ? (hold[1] ? "yes — " + hold[1] : "yes") : "no"
    }\ntokens:   ${tokens}\ncost:     $${totalCost.toFixed(4)} total${
      budgetExceeded(result)
        ? `\nbudget:   EXCEEDED — last turn spent $${
          Number(result?.total_cost_usd ?? 0).toFixed(4)
        } of $${env("CORO_MAX_BUDGET_USD") || "?"} cap`
        : ""
    }\nyield:    ${yieldDisplay}`,
  );
  if (!signal) warn(`warning: turn ${turn} has no YIELD line; protocol violation`);
  if (result) {
    const cw = extractContextWindow(result) ?? resolvedContextWindow(resolved);
    if (totalContext > tokenWarnThreshold(resolved, cw)) {
      warn(
        `warning: last turn used ${totalContext} input tokens — ${
          Math.trunc(totalContext / cw * 100)
        }% of ${m.model ?? DEFAULT_MODEL} context (${cw})`,
      );
    }
    if (resolved.spec && runtimeMax && runtimeMax < resolved.spec.maxOutput / 2) {
      warn(
        `note: runtime max-output cap is ${runtimeMax} tokens (${resolved.spec.id} can produce up to ${resolved.spec.maxOutput}); check CLAUDE_CODE_MAX_OUTPUT_TOKENS / ANTHROPIC_MAX_OUTPUT_TOKENS`,
      );
    }
  }
  if (totalCost > costWarnThreshold(resolved)) {
    warn(
      `warning: session cost $${formatCost(totalCost)} exceeds threshold $${
        formatCost(costWarnThreshold(resolved))
      }`,
    );
  }
}
/** Match Python's ties-to-even cents for exactly representable halfway values. */
export function formatCost(value: number): string {
  const scaled = Math.abs(value) * 100;
  // An exact binary halfway value at two decimal places has numerator divisible by 5².
  if (Number.isSafeInteger(scaled * 2) && scaled % 1 === 0.5 && (scaled * 2) % 25 === 0) {
    const lower = Math.floor(scaled);
    const rounded = lower % 2 === 0 ? lower : lower + 1;
    return (value < 0 ? "-" : "") + (rounded / 100).toFixed(2);
  }
  return value.toFixed(2);
}
function turns(root: string, arg?: string) {
  const s = resolveSessionArg(root, arg), files = logs(root, s);
  if (!files.length) die(`no turns found for session '${s}'`);
  console.log(`session: ${s}  model: ${loadMeta(root, s).model ?? "?"}`);
  for (const file of files) {
    const turn = Number(file.slice(0, -6));
    const events = text(join(turnsDir(root, s), file)).split(/\r?\n/).filter(Boolean).map((line) =>
      JSON.parse(line)
    );
    const result = extractResult(events), body = extractText(events);
    const summary = turn === 0 ? "(preamble)" : extractYield(body) ??
      `(no yield) ${(body.trim().split(/\r?\n/).at(-1) ?? "").slice(0, 60)}`;
    console.log(
      `  turn ${String(turn).padStart(3, "0")}  cost=${
        result ? "$" + Number(result.total_cost_usd ?? 0).toFixed(4) : "?"
      }  ${summary}`,
    );
  }
  console.log(`  total        $${sessionTotalCost(root, s).toFixed(4)}`);
}
function newPhase(root: string, slug: string, force: boolean) {
  const todo = join(root, ".cache", "TODO"),
    spec = join(todo, `phase-${slug}.md`),
    kickoff = join(todo, `phase-${slug}-kickoff.md`);
  if ((exists(spec) || exists(kickoff)) && !force) {
    die(`phase '${slug}' files already exist; use --force to overwrite`);
  }
  write(spec, text(join(skillRoot(), "templates", "phase.md")).replaceAll("{slug}", slug));
  write(
    kickoff,
    text(join(skillRoot(), "templates", "phase-kickoff.md")).replaceAll("{slug}", slug),
  );
  console.log(`created ${spec}`);
  console.log(`created ${kickoff}`);
}
export function sessionTotalCost(r: string, s: string) {
  return logs(r, s).reduce(
    (n, x) =>
      n +
      Number(
        extractResult(
          text(join(turnsDir(r, s), x)).split(/\r?\n/).filter(Boolean).map((
            line,
          ) => JSON.parse(line)),
        )?.total_cost_usd ?? 0,
      ),
    0,
  );
}
export class CliUsageError extends CoroError {}
const commandSyntax: Record<string, [number, number, string]> = {
  create: [1, 1, "<name>"],
  send: [0, 1, "[<name-or-slug>]"],
  status: [0, 1, "[<name-or-slug>]"],
  turns: [0, 1, "[<name-or-slug>]"],
  log: [0, 2, "[<name-or-slug>] [<turn>]"],
  use: [1, 1, "<name-or-slug>"],
  pop: [0, 0, ""],
  list: [0, 0, ""],
  hold: [0, Infinity, "[<name-or-slug>] [<reason> ...]"],
  unhold: [0, 1, "[<name-or-slug>]"],
  "new-phase": [1, 1, "<slug> [--force]"],
};
const help = [
  "usage: coro {create,send,status,turns,log,use,pop,list,hold,unhold,new-phase} ...",
  "",
  "Runtime config via env:",
  "  CORO_MODEL      alias (opus|sonnet|haiku|best), canonical id, or [1m]-suffixed;",
  "                  unknown slugs pass through with a warning. Default: sonnet.",
  "  CORO_EFFORT     low|medium|high|xhigh|max. If unset, the model default is used;",
  "                  does not inherit CLAUDE_CODE_EFFORT_LEVEL.",
  "  CORO_PROJECT    project root (default: auto-discover)",
  "  CORO_ADD_DIRS   colon-separated --add-dir paths",
  "  CORO_MAX_BUDGET_USD  per-turn budget cap (soft-fail in send, hard-fail in create)",
  "  CORO_TOKEN_WARN_RATIO / CORO_TOKEN_WARN / CORO_COST_WARN  override thresholds",
  "",
  "Subprocess env defaults (set when unset in parent):",
  "  API_TIMEOUT_MS=1200000  BASH_MAX_TIMEOUT_MS=1200000",
].join("\n");

/** Parse the supported interface; -- protects positional values from option parsing. */
export function parseCommand(argv: string[]) {
  const command = argv[0];
  if (command === "--help" || command === "-h") {
    return { command, args: [] as string[], force: false, help };
  }
  if (!command) throw new CliUsageError("a command is required");
  if (!Object.hasOwn(commandSyntax, command)) {
    throw new CliUsageError("invalid choice: '" + command + "'");
  }
  const args: string[] = [];
  let options = true, force = false;
  for (const arg of argv.slice(1)) {
    if (options && arg === "--") {
      options = false;
    } else if (options && (arg === "--help" || arg === "-h")) {
      return {
        command,
        args,
        force,
        help: ("usage: coro " + command + " " + commandSyntax[command][2]).trimEnd(),
      };
    } else if (options && command === "new-phase" && arg === "--force") {
      force = true;
    } else if (options && arg.startsWith("-") && arg !== "-" && !/^-\d+(?:\.\d+)?$/.test(arg)) {
      throw new CliUsageError("unrecognized argument: " + arg);
    } else {
      args.push(arg);
    }
  }
  const [min, max] = commandSyntax[command];
  if (args.length < min) throw new CliUsageError(command + " requires an argument");
  if (args.length > max) {
    throw new CliUsageError("unrecognized arguments: " + args.slice(max).join(" "));
  }
  if (command === "log" && args[1] !== undefined) {
    if (!/^[+-]?\d+(?:_\d+)*$/.test(args[1].trim())) {
      throw new CliUsageError("invalid integer value: '" + args[1] + "'");
    }
    args[1] = args[1].trim().replaceAll("_", "");
  }
  return { command, args, force, help: undefined };
}
export async function main(argv = Deno.args) {
  try {
    const { command: cmd, args, force, help: requestedHelp } = parseCommand(argv);
    if (requestedHelp !== undefined) {
      console.log(requestedHelp);
      return;
    }
    const root = findProjectRoot();
    if (cmd === "create") await create(root, args[0]);
    else if (cmd === "send") await send(root, args[0]);
    else if (cmd === "status") status(root, args[0]);
    else if (cmd === "turns") turns(root, args[0]);
    else if (cmd === "new-phase") newPhase(root, args[0], force);
    else if (cmd === "use") {
      const s = resolveSlug(root, args[0]);
      currentPush(root, s);
      console.error(`pushed ${s}`);
    } else if (cmd === "pop") {
      const x = currentPop(root);
      if (!x) die("CURRENT stack is empty");
      console.log(x);
    } else if (cmd === "list") {
      console.log(currentList(root).reverse().join("\n") || "(empty)");
    } else if (cmd === "hold") {
      const s = resolveSessionArg(root, args[0]);
      loadSession(root, s);
      const reason = args.slice(1).filter((part) => part.trim()).join(" ");
      writeHold(root, s, reason);
      console.log(`held session ${s}${reason ? ` — ${reason}` : ""}`);
    } else if (cmd === "unhold") {
      const s = resolveSessionArg(root, args[0]);
      loadSession(root, s);
      const x = clearHold(root, s);
      console.log(
        x === null ? `session ${s} was not held` : `unheld session ${s}${x ? ` (was: ${x})` : ""}`,
      );
    } else if (cmd === "log") {
      const s = resolveSessionArg(root, args[0]);
      const t = args[1] === undefined ? lastTurnNumber(root, s) : Number(args[1]);
      if (args[1] === undefined && t < 0) die(`no turns found for session '${s}'`);
      if (!exists(turnLogFile(root, s, t))) {
        die(`no log for turn ${t} of session '${s}'`);
      }
      writeAll(Deno.stdout, new TextEncoder().encode(text(turnLogFile(root, s, t))));
    } else die(`unknown command: ${cmd}`);
  } catch (e) {
    console.error(`error: ${e instanceof Error ? e.message : e}`);
    Deno.exit(e instanceof CliUsageError ? 2 : 1);
  }
}
if (import.meta.main) await main();
