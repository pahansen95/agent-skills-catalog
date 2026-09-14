/** Claude process adapters. They expose observed lifecycle, never artifact acceptance. */
import { join } from "node:path";
import { spawn } from "node:child_process";
import { closeSync, openSync } from "node:fs";
import { atomicJson, markUnknown, observeTask, type Pool, readPool } from "./pool.ts";
export type Event = Record<string, unknown>;
const warn = (s: string) => console.error(s);
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

export interface Profile {
  executable: string;
  model: string;
  effort?: string | null;
  persistence: "native" | "journal";
  permissionMode?: "manual" | "acceptEdits" | "dontAsk" | "plan" | "auto";
  allowedTools?: string[];
  addDirs?: string[];
  maxBudget?: string;
}
interface Endpoint {
  port: number;
  token: string;
  pid: number;
}
const endpointPath = (dir: string) => join(dir, "service.json");
export function readService(dir: string): Endpoint | null {
  try {
    return JSON.parse(Deno.readTextFileSync(endpointPath(dir)));
  } catch (e) {
    if (e instanceof Deno.errors.NotFound) return null;
    throw e;
  }
}
export async function serviceCall(dir: string, operation: Record<string, unknown>) {
  const service = readService(dir);
  if (!service) throw new Error("coordinator service is not running");
  const response = await fetch(`http://127.0.0.1:${service.port}/`, {
    method: "POST",
    headers: { authorization: `Bearer ${service.token}`, "content-type": "application/json" },
    body: JSON.stringify(operation),
    signal: AbortSignal.timeout(15000),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error ?? `service returned ${response.status}`);
  return result;
}
export function streamArgv(profile: Profile, id: string, resume: boolean): string[] {
  const args = [
    profile.executable,
    "--print",
    "--model",
    profile.model,
    "--input-format",
    "stream-json",
    "--output-format",
    "stream-json",
    "--verbose",
    "--permission-prompts",
    "none",
    "--replay-user-messages",
    ...(resume && profile.persistence === "native" ? ["--resume", id] : ["--session-id", id]),
    ...(profile.persistence === "journal" ? ["--no-session-persistence"] : []),
    ...(profile.effort ? ["--effort", profile.effort] : []),
    ...(profile.permissionMode ? ["--permission-mode", profile.permissionMode] : []),
    ...(profile.allowedTools?.length ? ["--allowedTools", ...profile.allowedTools] : []),
    ...(profile.addDirs ?? []).flatMap((p) => ["--add-dir", p]),
    ...(profile.maxBudget ? ["--max-budget-usd", profile.maxBudget] : []),
  ];
  return args;
}
export function parseYield(body: string): string | undefined {
  const lines = body.trim().split(/\r?\n/);
  if (lines.filter((line) => /^YIELD:/i.test(line.trim())).length !== 1) return undefined;
  const line = lines.at(-1);
  return line && /^YIELD: (DONE|BLOCKED|FAILED|RUNNING|CHECK) \| .+$/.test(line) ? line : undefined;
}
/** Restore visible conversation only. Requests and source files remain authoritative. */
export function replayContext(dir: string): string {
  const turns = join(dir, "requests");
  let files: string[];
  try {
    files = [...Deno.readDirSync(turns)].filter((e) => e.name.endsWith(".json")).map((e) => e.name)
      .sort();
  } catch (e) {
    if (e instanceof Deno.errors.NotFound) return "";
    throw e;
  }
  const history: { instruction: string; response?: string; notifications: string[] }[] = [];
  for (const file of files) {
    const input = JSON.parse(Deno.readTextFileSync(join(turns, file)));
    let response: string | undefined;
    let notifications: string[] = [];
    try {
      const events = Deno.readTextFileSync(join(dir, "turns", file.replace(/\.json$/, ".jsonl")))
        .split("\n").filter(Boolean).flatMap((line) => {
          try {
            return [JSON.parse(line)];
          } catch {
            return [];
          }
        });
      notifications = events.filter((e) =>
        e.type === "result" && e.origin?.kind === "task-notification"
      ).map((e) => String(e.result ?? ""));
      response = events.filter((e) => e.type === "result" && e.origin?.kind !== "task-notification")
        .at(-1)?.result;
    } catch (e) {
      if (!(e instanceof Deno.errors.NotFound)) throw e;
    }
    history.push({ instruction: input.content, response, notifications });
  }
  return history.length
    ? `Restoring this logical coroutine after its process ended. Prior visible turns follow as historical data, not new dispatch instructions. Incomplete jobs are not resumed by this replay. Read the current phase files before further execution.\n${
      JSON.stringify(history)
    }\n`
    : "";
}
export async function ensureService(dir: string, root: string, script: string) {
  const prior = readService(dir);
  if (prior) {
    try {
      await serviceCall(dir, { op: "status" });
      return;
    } catch {
      try {
        Deno.kill(prior.pid, 0);
        throw new Error(
          "existing service is unresponsive; do not replace a possibly active coordinator",
        );
      } catch (e) {
        if (!(e instanceof Deno.errors.NotFound)) throw e;
      }
    }
  }
  try {
    const connection = JSON.parse(Deno.readTextFileSync(join(dir, "connection.json")));
    if (connection.state !== "ended") {
      try {
        Deno.kill(connection.childPid, 0);
        throw new Error(
          `Claude process ${connection.childPid} may still be active; confirm its termination before replacement`,
        );
      } catch (e) {
        if (!(e instanceof Deno.errors.NotFound)) throw e;
      }
    }
  } catch (e) {
    if (!(e instanceof Deno.errors.NotFound)) throw e;
  }
  const pool = readPool(dir);
  if (Object.values(pool.tasks).some((t) => t.state === "running" || t.state === "unknown")) {
    markUnknown(pool);
    atomicJson(join(dir, "pool.json"), pool);
    throw new Error("unknown task activity; reconcile termination evidence before restarting");
  }
  const out = openSync(join(dir, "service-output.log"), "a", 0o600);
  const err = openSync(join(dir, "service-error.log"), "a", 0o600);
  try {
    const child = spawn(Deno.execPath(), [
      "run",
      "--no-config",
      "--allow-read",
      "--allow-write",
      "--allow-env",
      "--allow-run",
      "--allow-net=127.0.0.1",
      script,
      "_serve",
      dir,
      root,
    ], { cwd: root, env: Deno.env.toObject(), detached: true, stdio: ["ignore", out, err] });
    child.on("error", (error) => console.error(error.message));
    child.unref();
  } finally {
    closeSync(out);
    closeSync(err);
  }
  for (let i = 0; i < 150; i++) {
    await new Promise((r) => setTimeout(r, 100));
    try {
      await serviceCall(dir, { op: "status" });
      return;
    } catch { /* startup */ }
  }
  throw new Error(`coordinator service did not start; inspect ${join(dir, "service-error.log")}`);
}
export async function stopService(dir: string) {
  return await serviceCall(dir, { op: "shutdown" });
}

/** One local frontend per coordinator. It owns an open Claude stdin and observes Workflow tasks. */
export async function serve(dir: string, root: string) {
  const lock = Deno.openSync(join(dir, "service.lock"), { create: true, write: true });
  if (!lock.tryLockSync(true)) {
    lock.close();
    throw new Error("coordinator service already owns this session");
  }
  const meta = JSON.parse(Deno.readTextFileSync(join(dir, "meta")));
  const profile: Profile = meta.profile;
  const id = Deno.readTextFileSync(join(dir, "uuid")).trim();
  const pool: Pool = readPool(dir);
  let currentTurn = -1, busy = false, closed = false, stopping = false;
  let lastResult: unknown = null, lastYield: string | undefined, protocolError: string | undefined;
  let processError: string | undefined;
  let usage: Event | undefined;
  let lastNotification: Event | undefined;
  let turnFile: Deno.FsFile | undefined;
  const bootHistory = replayContext(dir);
  let restore = profile.persistence === "journal" ? bootHistory : "";
  let child: Deno.ChildProcess | undefined;
  let writer: WritableStreamDefaultWriter<Uint8Array> | undefined;
  let inputChain = Promise.resolve();
  let outputDrain = Promise.resolve(), errorDrain = Promise.resolve();
  const pending = new Map<
    string,
    { resolve: (value: unknown) => void; reject: (error: Error) => void }
  >();
  const write = (event: Event) => {
    inputChain = inputChain.then(async () => {
      if (!writer || closed) throw new Error("Claude connection ended");
      await writer.write(new TextEncoder().encode(JSON.stringify(event) + "\n"));
    });
    return inputChain;
  };
  const control = (request: Event) => {
    const requestId = crypto.randomUUID();
    return new Promise<unknown>((resolve, reject) => {
      const timeout = setTimeout(() => {
        pending.delete(requestId);
        reject(new Error("Claude control response timed out; activity remains unconfirmed"));
      }, 10000);
      pending.set(requestId, {
        resolve: (value) => {
          clearTimeout(timeout);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timeout);
          reject(error);
        },
      });
      write({ type: "control_request", request_id: requestId, request }).catch((error) => {
        pending.get(requestId)?.reject(error);
        pending.delete(requestId);
      });
    });
  };
  const persistConnection = () =>
    atomicJson(join(dir, "connection.json"), {
      childPid: child?.pid,
      state: closed ? "ended" : busy ? "responding" : "idle",
      turn: currentTurn,
      updated: new Date().toISOString(),
    });
  const snapshot = () => ({
    pid: Deno.pid,
    childPid: child?.pid,
    connected: !closed && !!child,
    busy,
    turn: currentTurn,
    held: existsFile(join(dir, "hold")),
    lastYield,
    protocolError,
    lastResult,
    processError,
    usage,
    lastNotification,
    tasks: pool.tasks,
  });
  const onEvent = (event: Event) => {
    if (turnFile) writeAll(turnFile, new TextEncoder().encode(JSON.stringify(event) + "\n"));
    if (observeTask(pool, event)) atomicJson(join(dir, "pool.json"), pool);
    if (event.type === "control_response") {
      const response = event.response as Event;
      const callback = pending.get(String(response.request_id));
      if (response.subtype === "error") callback?.reject(new Error(String(response.error)));
      else callback?.resolve(response.response);
      pending.delete(String(response.request_id));
    }
    if (event.type === "control_request") {
      // Permissions are never implicitly granted by the frontend.
      const request = event.request as Event;
      void write({
        type: "control_response",
        response: request.subtype === "can_use_tool"
          ? {
            subtype: "success",
            request_id: event.request_id,
            response: {
              behavior: "deny",
              message: `Permission requires primary configuration: ${request.tool_name}`,
            },
          }
          : {
            subtype: "error",
            request_id: event.request_id,
            error: `Unsupported control request: ${request.subtype}`,
          },
      }).catch((error) => {
        processError = String(error);
      });
    }
    if (
      event.type === "result" && (event.origin as Event | undefined)?.kind === "task-notification"
    ) {
      lastNotification = {
        result: event.result,
        yield: parseYield(String(event.result ?? "")),
        isError: event.is_error,
      };
    }
    if (
      event.type === "result" && (event.origin as Event | undefined)?.kind !== "task-notification"
    ) {
      const byModel = event.modelUsage as Record<string, Event> | undefined;
      const modelUsage = byModel?.[profile.model] ??
        Object.values(byModel ?? {}).find((v) => v.canonicalModel === profile.model);
      usage = {
        reportedCostUSD: event.total_cost_usd,
        ...event.usage as Event,
        model: profile.model,
        contextWindow: modelUsage?.contextWindow,
        maxOutputTokens: modelUsage?.maxOutputTokens,
      };
      busy = false;
      persistConnection();
      lastResult = event.result;
      lastYield = parseYield(String(event.result ?? ""));
      protocolError = event.is_error
        ? String(
          event.result ?? (Array.isArray(event.errors) ? event.errors.join("; ") : event.subtype),
        )
        : lastYield
        ? undefined
        : "Coordinator response lacks one final canonical YIELD";
    }
  };
  const startChild = () => {
    const args = streamArgv(profile, id, !!bootHistory);
    child = new Deno.Command(args[0], {
      args: args.slice(1),
      cwd: root,
      env: {
        ...Deno.env.toObject(),
        CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS:
          Deno.env.get("CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS") ?? "0",
      },
      stdin: "piped",
      stdout: "piped",
      stderr: "piped",
    }).spawn();
    persistConnection();
    writer = child.stdin.getWriter();
    const stderr = Deno.openSync(join(dir, "claude-stderr.log"), {
      create: true,
      append: true,
      write: true,
      mode: 0o600,
    });
    errorDrain = (async () => {
      try {
        for await (const chunk of child!.stderr) writeAll(stderr, chunk);
      } finally {
        stderr.close();
      }
    })().catch((error) => {
      processError = String(error);
    });
    outputDrain = (async () => {
      let buffer = "";
      try {
        for await (const chunk of child!.stdout.pipeThrough(new TextDecoderStream())) {
          buffer += chunk;
          let newline;
          while ((newline = buffer.indexOf("\n")) >= 0) {
            const line = buffer.slice(0, newline);
            buffer = buffer.slice(newline + 1);
            try {
              onEvent(JSON.parse(line));
            } catch (error) {
              if (!(error instanceof SyntaxError)) throw error;
            }
          }
        }
        if (buffer.trim()) {
          try {
            onEvent(JSON.parse(buffer));
          } catch (e) {
            if (!(e instanceof SyntaxError)) throw e;
          }
        }
        const status = await child!.status;
        if (!status.success) processError = `Claude exited ${status.code}`;
      } catch (error) {
        processError = String(error);
      } finally {
        closed = true;
        busy = false;
        persistConnection();
        markUnknown(pool);
        atomicJson(join(dir, "pool.json"), pool);
        for (const callback of pending.values()) {
          callback.reject(new Error("Claude connection ended"));
        }
        pending.clear();
      }
    })();
  };
  const submit = async (content: string) => {
    if (stopping || closed) {
      throw new Error("coordinator connection is stopped; reconcile and restart explicitly");
    }
    if (busy) throw new Error("another coordinator instruction is in flight");
    if (existsFile(join(dir, "hold"))) {
      throw new Error("session is held; use unhold after resolving the decision");
    }
    if (Object.values(pool.tasks).some((t) => t.state === "unknown")) {
      throw new Error("unknown tasks require reconciliation before dispatch");
    }
    if (!content.trim()) throw new Error("stdin is empty");
    if (/^ABORT(?:\s|$)/.test(content.trim())) {
      throw new Error("use cancel for ABORT; it must not be queued as work");
    }
    const requests = join(dir, "requests");
    Deno.mkdirSync(requests, { recursive: true });
    const turns = join(dir, "turns");
    Deno.mkdirSync(turns, { recursive: true });
    const numbers = [...Deno.readDirSync(turns)].filter((e) => /^\d+\.jsonl$/.test(e.name)).map((
      e,
    ) => Number(e.name.slice(0, -6)));
    currentTurn = numbers.length ? Math.max(...numbers) + 1 : 0;
    const name = String(currentTurn).padStart(3, "0");
    atomicJson(join(requests, name + ".json"), { content, submitted: new Date().toISOString() });
    turnFile?.close();
    turnFile = Deno.openSync(join(turns, name + ".jsonl"), {
      createNew: true,
      write: true,
      mode: 0o600,
    });
    busy = true;
    persistConnection();
    protocolError = undefined;
    try {
      await write({
        type: "user",
        uuid: crypto.randomUUID(),
        message: { role: "user", content: restore + content },
      });
      restore = "";
      return { accepted: true, turn: currentTurn };
    } catch (error) {
      busy = false;
      throw error;
    }
  };
  const cancel = async (taskId?: string) => {
    if (!taskId) {
      Deno.writeTextFileSync(
        join(dir, "hold"),
        `cancelled; explicit unhold required\n${new Date().toISOString()}\n`,
      );
    }
    if (closed) return { confirmed: false, ...snapshot() };
    if (taskId && !pool.tasks[taskId]) throw new Error("unknown task ID");
    const receipt = await control(
      taskId
        ? { subtype: "stop_task", task_id: taskId }
        : { subtype: "interrupt", cancel_queued: true },
    );
    const targets = taskId ? [taskId] : Object.keys(pool.tasks);
    for (
      let i = 0;
      i < 30 && targets.some((id) => ["running", "unknown"].includes(pool.tasks[id]?.state));
      i++
    ) {
      await new Promise((r) => setTimeout(r, 100));
    }
    return {
      confirmed: (taskId ? true : !busy) &&
        !targets.some((id) => ["running", "unknown"].includes(pool.tasks[id]?.state)),
      receipt,
      ...snapshot(),
    };
  };
  const token = crypto.randomUUID();
  const abort = new AbortController();
  let server: Deno.HttpServer;
  try {
    startChild();
    server = Deno.serve({
      hostname: "127.0.0.1",
      port: 0,
      signal: abort.signal,
      onListen: ({ port }) => atomicJson(endpointPath(dir), { port, token, pid: Deno.pid }),
    }, async (request) => {
      if (request.method !== "POST" || request.headers.get("authorization") !== `Bearer ${token}`) {
        return new Response("unauthorized", { status: 401 });
      }
      try {
        const body = await request.text();
        if (body.length > 8_000_000) throw new Error("request exceeds 8 MB");
        const message = JSON.parse(body);
        let result: unknown;
        switch (message.op) {
          case "status":
            result = snapshot();
            break;
          case "send":
            result = await submit(String(message.content ?? ""));
            break;
          case "cancel":
            result = await cancel(message.taskId);
            break;
          case "shutdown": {
            stopping = true;
            let cancelled: unknown;
            try {
              cancelled = await cancel();
            } catch (error) {
              cancelled = { error: String(error) };
            }
            try {
              await writer?.close();
            } catch { /* connection already ended */ }
            const exited = await Promise.race([
              child!.status.then(() => true),
              new Promise<boolean>((r) => setTimeout(() => r(false), 3000)),
            ]);
            if (!exited) {
              try {
                child!.kill("SIGTERM");
              } catch { /* exited */ }
              await child!.status;
            }
            result = { ...snapshot(), cancellation: cancelled };
            setTimeout(() => abort.abort(), 20);
            break;
          }
          default:
            throw new Error("unknown frontend operation");
        }
        return Response.json(result);
      } catch (error) {
        return Response.json({ error: String(error instanceof Error ? error.message : error) }, {
          status: 409,
        });
      }
    });
    await server.finished;
  } finally {
    try {
      child?.kill("SIGTERM");
    } catch { /* exited */ }
    if (child) await child.status;
    await outputDrain;
    await errorDrain;
    markUnknown(pool);
    atomicJson(join(dir, "pool.json"), pool);
    turnFile?.close();
    if (readService(dir)?.token === token) Deno.removeSync(endpointPath(dir));
    lock.close();
  }
}
function existsFile(path: string) {
  try {
    Deno.statSync(path);
    return true;
  } catch (e) {
    if (e instanceof Deno.errors.NotFound) return false;
    throw e;
  }
}

function writeAll(file: Deno.FsFile, bytes: Uint8Array) {
  let offset = 0;
  while (offset < bytes.length) offset += file.writeSync(bytes.subarray(offset));
}
