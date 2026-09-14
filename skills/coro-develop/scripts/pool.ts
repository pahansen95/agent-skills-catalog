/** Durable observations and immutable dispatch evidence. Workflow owns scheduling. */
import { dirname, join, resolve } from "node:path";

export type TaskState = "running" | "completed" | "failed" | "cancelled" | "unknown";
export interface Task {
  id: string;
  state: TaskState;
  description?: string;
  type?: string;
  updated: string;
  evidence?: string;
}
export interface Pool {
  tasks: Record<string, Task>;
}
const path = (directory: string) => join(directory, "pool.json");
export function atomicJson(file: string, value: unknown) {
  Deno.mkdirSync(dirname(file), { recursive: true });
  const temp = file + "." + crypto.randomUUID() + ".tmp";
  try {
    Deno.writeTextFileSync(temp, JSON.stringify(value, null, 2) + "\n", { mode: 0o600 });
    Deno.renameSync(temp, file);
  } finally {
    try {
      Deno.removeSync(temp);
    } catch (e) {
      if (!(e instanceof Deno.errors.NotFound)) {
        console.error(`temporary-file cleanup failed: ${e}`);
      }
    }
  }
}
export function readPool(directory: string): Pool {
  try {
    return JSON.parse(Deno.readTextFileSync(path(directory)));
  } catch (e) {
    if (e instanceof Deno.errors.NotFound) return { tasks: {} };
    throw e;
  }
}
export function observeTask(pool: Pool, event: Record<string, unknown>): boolean {
  if (event.type !== "system" || typeof event.task_id !== "string") return false;
  const subtype = event.subtype;
  if (!["task_started", "task_progress", "task_notification"].includes(String(subtype))) {
    return false;
  }
  const id = event.task_id, previous = pool.tasks[id];
  let state: TaskState = previous?.state ?? "running";
  if (subtype === "task_notification") {
    state = event.status === "completed"
      ? "completed"
      : event.status === "failed"
      ? "failed"
      : ["stopped", "cancelled"].includes(String(event.status))
      ? "cancelled"
      : "unknown";
  } else if (previous && previous.state !== "running") return false;
  pool.tasks[id] = {
    ...previous,
    id,
    state,
    updated: new Date().toISOString(),
    ...(typeof event.description === "string" ? { description: event.description } : {}),
    ...(typeof event.task_type === "string" ? { type: event.task_type } : {}),
  };
  return true;
}
export function markUnknown(pool: Pool) {
  for (const task of Object.values(pool.tasks)) {
    if (task.state === "running") {
      task.state = "unknown";
      task.updated = new Date().toISOString();
    }
  }
}
export function reconcileTask(directory: string, id: string, state: TaskState, evidence: string) {
  if (!["completed", "failed", "cancelled"].includes(state)) {
    throw new Error("reconcile requires a terminal observation");
  }
  if (!evidence.trim()) throw new Error("reconcile requires termination evidence");
  const pool = readPool(directory), task = pool.tasks[id];
  if (!task || task.state !== "unknown") throw new Error("only unknown tasks may be reconciled");
  task.state = state;
  task.evidence = evidence;
  task.updated = new Date().toISOString();
  atomicJson(path(directory), pool);
}
export async function digest(file: string) {
  const hash = await crypto.subtle.digest("SHA-256", await Deno.readFile(file));
  return [...new Uint8Array(hash)].map((x) => x.toString(16).padStart(2, "0")).join("");
}
export interface AttemptInput {
  id: string;
  request: string;
  script?: string;
  inputs?: string[];
  outputs?: string[];
  checks?: string[];
  previous?: string;
}
function validId(id: string) {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(id)) throw new Error("invalid attempt ID");
}
/** Snapshot first, publish manifest last. Existing attempts cannot be overwritten. */
export async function snapshotAttempt(directory: string, input: AttemptInput) {
  validId(input.id);
  const target = join(directory, "attempts", input.id);
  Deno.mkdirSync(dirname(target), { recursive: true });
  Deno.mkdirSync(target); // exclusive creation; collisions are an error
  const files: Record<string, string> = {};
  for (
    const [label, file] of [["request.md", input.request], ["workflow.js", input.script]] as const
  ) {
    if (file) {
      Deno.copyFileSync(file, join(target, label));
      files[label] = await digest(join(target, label));
    }
  }
  const inputs: Record<string, string> = {};
  for (const file of input.inputs ?? []) inputs[resolve(file)] = await digest(file);
  const manifest = {
    ...input,
    request: "request.md",
    script: input.script ? "workflow.js" : undefined,
    files,
    inputs,
    outputs: (input.outputs ?? []).map((p) => resolve(p)),
    created: new Date().toISOString(),
  };
  atomicJson(join(target, "manifest.json"), manifest);
  return manifest;
}
export function readAttempts(directory: string) {
  try {
    return [...Deno.readDirSync(join(directory, "attempts"))].filter((e) => e.isDirectory)
      .map((e) => {
        try {
          return JSON.parse(
            Deno.readTextFileSync(join(directory, "attempts", e.name, "manifest.json")),
          );
        } catch {
          return { id: e.name, incomplete: true };
        }
      });
  } catch (e) {
    if (e instanceof Deno.errors.NotFound) return [];
    throw e;
  }
}

/** Seal observed outputs and supplied check evidence, without granting acceptance. */
export async function sealAttempt(directory: string, id: string, evidence: unknown) {
  validId(id);
  const target = join(directory, "attempts", id);
  const manifest = JSON.parse(Deno.readTextFileSync(join(target, "manifest.json")));
  const outputs: Record<string, string> = {};
  for (const file of manifest.outputs) outputs[file] = await digest(file);
  const result = { outputs, evidence, recorded: new Date().toISOString() };
  Deno.writeTextFileSync(join(target, "result.json"), JSON.stringify(result, null, 2) + "\n", {
    createNew: true,
    mode: 0o600,
  });
  return result;
}
/** A successful comparison proves matching bytes, not the correctness of any claim. */
export async function checkAttempt(directory: string, id: string) {
  validId(id);
  const target = join(directory, "attempts", id);
  const manifest = JSON.parse(Deno.readTextFileSync(join(target, "manifest.json")));
  const changes: string[] = [];
  const compare = async (files: Record<string, string>, base = "") => {
    for (const [file, expected] of Object.entries(files)) {
      const full = base ? join(base, file) : file;
      try {
        if (await digest(full) !== expected) changes.push(full);
      } catch (e) {
        if (e instanceof Deno.errors.NotFound) changes.push(full);
        else throw e;
      }
    }
  };
  await compare(manifest.files, target);
  await compare(manifest.inputs);
  let sealed = false;
  try {
    const result = JSON.parse(Deno.readTextFileSync(join(target, "result.json")));
    sealed = true;
    await compare(result.outputs);
  } catch (e) {
    if (!(e instanceof Deno.errors.NotFound)) throw e;
  }
  return { id, sealed, unchanged: sealed && changes.length === 0, changes };
}
