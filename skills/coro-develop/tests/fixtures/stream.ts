/** Interactive Claude fixture: real pipes and timers, no models or network. */
const emit = (event: unknown) => console.log(JSON.stringify(event));
const result = (body = "YIELD: DONE | observed") => emit({ type: "result", result: body });
let keepAlive = false;
let running = false, responseTimer: number | undefined;
Deno.writeTextFileSync(
  Deno.env.get("CORO_TEST_CAPTURE")!,
  JSON.stringify({ args: Deno.args, pid: Deno.pid }) + "\n",
  { append: true },
);
for await (
  const chunk of Deno.stdin.readable.pipeThrough(new TextDecoderStream()).pipeThrough(
    new TransformStream<string, string>(
      {
        start() {
          this.buffer = "";
        },
        transform(chunk, controller) {
          this.buffer += chunk;
          let index;
          while ((index = this.buffer.indexOf("\n")) >= 0) {
            controller.enqueue(this.buffer.slice(0, index));
            this.buffer = this.buffer.slice(index + 1);
          }
        },
        buffer: "",
      } as Transformer<string, string> & { buffer: string },
    ),
  )
) {
  const event = JSON.parse(chunk);
  if (event.type === "control_request") {
    if (running && Deno.env.get("CORO_TEST_CANCEL") !== "missing") {
      running = false;
      emit({
        type: "system",
        subtype: "task_notification",
        task_id: "workflow-1",
        status: "stopped",
      });
    }
    if (responseTimer !== undefined) {
      clearTimeout(responseTimer);
      responseTimer = undefined;
      result("YIELD: DONE | interrupted");
    }
    emit({
      type: "control_response",
      response: { subtype: "success", request_id: event.request_id, response: {} },
    });
    continue;
  }
  if (event.type !== "user") continue;
  const content = String(event.message.content);
  Deno.writeTextFileSync(Deno.env.get("CORO_TEST_MESSAGES")!, JSON.stringify({ content }) + "\n", {
    append: true,
  });
  if (content === "crash") Deno.exit(17);
  if (content === "linger") keepAlive = true;
  if (content === "start") {
    running = true;
    emit({ type: "system", subtype: "task_started", task_id: "workflow-1", task_type: "workflow" });
    result("YIELD: RUNNING | workflow-1");
  } else if (content === "complete") {
    running = false;
    emit({
      type: "system",
      subtype: "task_notification",
      task_id: "workflow-1",
      status: "completed",
    });
    result();
  } else if (content === "slow") {
    responseTimer = setTimeout(() => {
      responseTimer = undefined;
      result();
    }, 800);
    emit({ type: "result", result: "background", origin: { kind: "task-notification" } });
  } else if (content === "bad-yield") result("YIELD: DONE | early\nYIELD: CHECK | duplicate");
  else result();
}
if (responseTimer !== undefined) clearTimeout(responseTimer);

if (keepAlive) await new Promise((r) => setTimeout(r, 60000));
