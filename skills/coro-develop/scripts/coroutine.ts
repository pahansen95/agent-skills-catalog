#!/usr/bin/env -S deno run
/** Stateful Claude session manager.  The files it writes are deliberately
 * compatible with the former Python implementation. */
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  ensureService,
  type ProcessRunner,
  type Profile,
  readService,
  serve,
  serviceCall,
  stopService,
  SubprocessRunner,
} from "./transport.ts";
export { type ProcessRunner, SubprocessRunner } from "./transport.ts";
import {
  atomicJson,
  checkAttempt,
  markUnknown,
  readAttempts,
  readPool,
  reconcileTask,
  sealAttempt,
  snapshotAttempt,
  type TaskState,
} from "./pool.ts";

export class CoroError extends Error {}
type Event = Record<string, unknown>;
const DEFAULT_MODEL = "sonnet";
import { type Spec, specs } from "./models.ts";
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
  if (arg.includes("/") || arg === "." || arg === "..") die("session names cannot contain paths");
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
    env("CORO_CLAUDE", "claude"),
    "--print",
    "--model",
    r.claudeArg,
    ...flags(r),
    ...(sessionId ? ["--session-id", sessionId] : ["--resume", resume!]),
    ...(maxBudget ? ["--max-budget-usd", maxBudget] : []),
  ];
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
function preamble(role = "worker") {
  const path = join(skillRoot(), "role", `${role}.md`);
  if (!exists(path)) die(`role/worker.md not found at ${path}`);
  return `${text(path).trim()}\n\nAcknowledge this role and wait for your first instruction.`;
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
function coordinator(root: string, slug: string) {
  return loadMeta(root, slug).role === "coordinator";
}
function identifier(value: string) {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(value)) {
    die("invalid name: use letters, digits, underscores or hyphens");
  }
}
export function connectionProfile(): Profile {
  const r = resolve(env("CORO_MODEL", DEFAULT_MODEL), env("CORO_EFFORT"));
  r.warnings.forEach(warn);
  const persistence = env("CORO_PERSISTENCE", "native");
  if (persistence !== "native" && persistence !== "journal") {
    die("CORO_PERSISTENCE must be native or journal");
  }
  const permissionMode = env("CORO_PERMISSION_MODE");
  if (
    permissionMode && !["manual", "acceptEdits", "dontAsk", "plan", "auto"].includes(permissionMode)
  ) die("unsupported CORO_PERMISSION_MODE");
  const allowedTools = JSON.parse(env("CORO_ALLOWED_TOOLS", "[]"));
  if (!Array.isArray(allowedTools) || !allowedTools.every((v) => typeof v === "string")) {
    die("CORO_ALLOWED_TOOLS must be a JSON string array");
  }
  return {
    executable: env("CORO_CLAUDE", "claude"),
    model: r.spec ? r.spec.id + (r.extended ? "[1m]" : "") : r.claudeArg,
    effort: r.effort,
    persistence: persistence as Profile["persistence"],
    permissionMode: permissionMode as Profile["permissionMode"] || undefined,
    allowedTools,
    addDirs: env("CORO_ADD_DIRS").split(":").map((v) => v.trim()).filter(Boolean),
    maxBudget: env("CORO_MAX_BUDGET_USD") || undefined,
  };
}
async function create(root: string, name: string) {
  identifier(name);
  const role = env("CORO_ROLE", "coordinator");
  if (role === "worker") return await createWorker(root, name);
  if (role !== "coordinator") die("CORO_ROLE must be coordinator or worker");
  if (parseSlug(name)) die("pick a name without a trailing _<digits>");
  const slug = makeSlug(name), dir = slugDir(root, slug), profile = connectionProfile();
  if (exists(dir)) die(`slug '${slug}' already exists`);
  Deno.mkdirSync(coroDir(root), { recursive: true });
  Deno.mkdirSync(dir, { mode: 0o700 });
  saveSession(root, slug, crypto.randomUUID(), profile.model);
  atomicJson(metaFile(root, slug), { role, model: profile.model, profile });
  currentPush(root, slug);
  await ensureService(dir, root, fileURLToPath(import.meta.url));
  await serviceCall(dir, { op: "send", content: preamble("coordinator") });
  console.log(slug);
  console.error(
    "Role submitted; inspect status before the first instruction. Creation does not consume stdin.",
  );
}
async function send(root: string, arg?: string) {
  const slug = resolveSessionArg(root, arg);
  loadSession(root, slug);
  if (!coordinator(root, slug)) return await sendWorker(root, slug);
  if (readHold(root, slug)[0]) die("session is held; use unhold after resolving the decision");
  const content = (await new Response(Deno.stdin.readable).text()).trim();
  if (!content) die("stdin is empty");
  const dir = slugDir(root, slug);
  await ensureService(dir, root, fileURLToPath(import.meta.url));
  console.log(JSON.stringify(await serviceCall(dir, { op: "send", content })));
}
async function coordinatorStatus(root: string, slug: string) {
  const dir = slugDir(root, slug);
  try {
    console.log(JSON.stringify(await serviceCall(dir, { op: "status" }), null, 2));
  } catch (error) {
    console.log(
      JSON.stringify(
        {
          connected: false,
          observationError: String(error),
          held: readHold(root, slug)[0],
          tasks: readPool(dir).tasks,
          recovery: "Inspect service logs and task termination before restarting.",
        },
        null,
        2,
      ),
    );
  }
}
async function createWorker(root: string, name: string) {
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
async function sendWorker(root: string, arg?: string) {
  const slug = resolveSessionArg(root, arg),
    id = loadSession(root, slug),
    meta = loadMeta(root, slug),
    model = String(meta.model ?? env("CORO_MODEL", DEFAULT_MODEL)),
    r = resolve(model, env("CORO_EFFORT"));
  r.warnings.forEach(warn);
  const content = (await new Response(Deno.stdin.readable).text()).trim();
  if (!content) die("stdin is empty");
  if (readHold(root, slug)[0]) {
    die(`session '${slug}' is held; use unhold after resolving the decision`);
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
  identifier(slug);
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
  persistence: [2, 2, "<session> <native|journal> (frontend must be stopped)"],
  cancel: [0, 2, "[<session>] [<task-id>]"],
  shutdown: [0, 1, "[<session>]"],
  jobs: [0, 1, "[<session>]"],
  attempt: [0, 1, "[<session>] < attempt.json"],
  attempts: [0, 1, "[<session>]"],
  "attempt-seal": [2, 2, "<session> <attempt-id> < result.json"],
  "attempt-check": [2, 2, "<session> <attempt-id>"],
  reconcile: [4, Infinity, "<session> <task-id> <completed|failed|cancelled> <evidence>"],
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
  `usage: coro {${Object.keys(commandSyntax).join(",")}} ...`,
  "",
  "Coordinator create/send return submission acknowledgments. Inspect status/log/jobs.",
  "cancel uses Claude controls; shutdown closes the frontend. Neither accepts artifacts.",
  "attempt snapshots {id,request,script?,inputs?,outputs?,checks?,previous?} from stdin JSON.",
  "attempt-seal records result evidence + output hashes once; attempt-check detects changes.",
  "reconcile requires a stopped frontend and explicit termination evidence for unknown tasks.",
  "",
  "  CORO_ROLE       coordinator (default) or worker; existing roles are retained",
  "  CORO_CLAUDE     executable path (default: claude)",
  "  CORO_PERSISTENCE native (default) or journal (visible-history recovery)",
  "  CORO_PERMISSION_MODE optional explicit Claude permission mode; no bypass",
  "  CORO_ALLOWED_TOOLS JSON array of allowed Claude tool patterns",
  "  Coordinator connection settings are saved at create and reused.",
  "",
  "Runtime config via env:",
  "  CORO_MODEL      alias (fable|opus|sonnet|haiku|best), canonical id, or [1m]-suffixed;",
  "                  unknown slugs pass through with a warning. Default: sonnet.",
  "  CORO_EFFORT     low|medium|high|xhigh|max. If unset, the model default is used;",
  "                  does not inherit CLAUDE_CODE_EFFORT_LEVEL.",
  "  CORO_PROJECT    project root (default: auto-discover)",
  "  CORO_ADD_DIRS   colon-separated --add-dir paths",
  "  CORO_MAX_BUDGET_USD  Claude process budget cap (per turn for legacy workers)",
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
    if (argv[0] === "_serve" && argv.length === 3) return await serve(argv[1], argv[2]);
    const { command: cmd, args, force, help: requestedHelp } = parseCommand(argv);
    if (requestedHelp !== undefined) {
      console.log(requestedHelp);
      return;
    }
    const root = findProjectRoot();
    if (cmd === "create") await create(root, args[0]);
    else if (cmd === "send") await send(root, args[0]);
    else if (cmd === "status") {
      const slug = resolveSessionArg(root, args[0]);
      if (coordinator(root, slug)) await coordinatorStatus(root, slug);
      else status(root, slug);
    } else if (
      [
        "cancel",
        "shutdown",
        "jobs",
        "attempt",
        "attempts",
        "attempt-seal",
        "attempt-check",
        "reconcile",
      ].includes(cmd)
    ) {
      const slug = resolveSessionArg(root, args[0]), dir = slugDir(root, slug);
      let result: unknown;
      if (cmd === "jobs") result = readPool(dir);
      else if (cmd === "attempts") result = readAttempts(dir);
      else if (cmd === "attempt") {
        result = await snapshotAttempt(
          dir,
          JSON.parse(await new Response(Deno.stdin.readable).text()),
        );
      } else if (cmd === "attempt-seal") {
        result = await sealAttempt(
          dir,
          args[1],
          JSON.parse(await new Response(Deno.stdin.readable).text()),
        );
      } else if (cmd === "attempt-check") result = await checkAttempt(dir, args[1]);
      else if (cmd === "reconcile") {
        const endpoint = readService(dir);
        if (endpoint) {
          try {
            Deno.kill(endpoint.pid, 0);
            die("stop the frontend before reconciling");
          } catch (e) {
            if (!(e instanceof Deno.errors.NotFound)) throw e;
          }
        }
        const pool = readPool(dir);
        markUnknown(pool);
        atomicJson(join(dir, "pool.json"), pool);
        reconcileTask(dir, args[1], args[2] as TaskState, args.slice(3).join(" "));
        result = readPool(dir);
      } else {
        if (!coordinator(root, slug)) die("control commands require a coordinator session");
        result = cmd === "shutdown"
          ? await stopService(dir)
          : await serviceCall(dir, { op: "cancel", taskId: args[1] });
      }
      console.log(JSON.stringify(result, null, 2));
    } else if (cmd === "persistence") {
      const slug = resolveSessionArg(root, args[0]), dir = slugDir(root, slug);
      const meta = loadMeta(root, slug);
      if (!coordinator(root, slug)) die("persistence configuration requires a coordinator");
      if (!["native", "journal"].includes(args[1])) die("persistence must be native or journal");
      if (readService(dir)) die("shutdown the frontend before changing persistence");
      if (
        Object.values(readPool(dir).tasks).some((t) => ["running", "unknown"].includes(t.state))
      ) die("reconcile task termination before changing persistence");
      const connectionPath = join(dir, "connection.json");
      if (exists(connectionPath)) {
        const connection = JSON.parse(text(connectionPath));
        if (connection.state !== "ended") {
          try {
            Deno.kill(connection.childPid, 0);
            die("Claude may still be active");
          } catch (e) {
            if (!(e instanceof Deno.errors.NotFound)) throw e;
          }
        }
      }
      (meta.profile as Profile).persistence = args[1] as Profile["persistence"];
      atomicJson(metaFile(root, slug), meta);
      console.log(`persistence=${args[1]}; next send reconnects explicitly`);
    } else if (cmd === "turns") turns(root, args[0]);
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
