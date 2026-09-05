// Local stream-json fixture; never invokes Claude or accesses the network.
const args = Deno.args;
const payload = JSON.parse(await new Response(Deno.stdin.readable).text());
const creating = args.includes("--session-id");
const id = args[args.indexOf(creating ? "--session-id" : "--resume") + 1];
const mode = Deno.env.get("CORO_TEST_MODE") ?? "normal";
Deno.writeTextFileSync(
  Deno.env.get("CORO_TEST_CAPTURE")!,
  JSON.stringify({
    args,
    payload,
    cwd: Deno.cwd(),
    timeout: Deno.env.get("API_TIMEOUT_MS"),
    bashTimeout: Deno.env.get("BASH_MAX_TIMEOUT_MS"),
  }) + "\n",
  { append: true, create: true },
);
const emit = (event: unknown) => console.log(JSON.stringify(event));
emit({ type: "system", session_id: mode === "mismatch" ? "different-uuid" : id });
if (mode === "tools") {
  emit({
    type: "assistant",
    message: { content: [{ type: "tool_use", name: "Read", input: { path: "file" } }] },
  });
  emit({
    type: "user",
    message: { content: [{ type: "tool_result", tool_use_id: "abcdefghijklmnop" }] },
  });
}
emit({
  type: "assistant",
  message: {
    content: [{
      type: "text",
      text: mode === "no-yield" ? "plain response" : "résumé 🧪\nYIELD: DONE | checked",
    }],
  },
});
const budget = mode === "budget" || (mode === "inline-budget" && !creating);
if (mode === "pause") {
  const deadline = Date.now() + 10000;
  for (;;) {
    try {
      Deno.statSync(Deno.env.get("CORO_TEST_GATE")!);
      break;
    } catch (error) {
      if (!(error instanceof Deno.errors.NotFound)) throw error;
    }
    if (Date.now() > deadline) throw new Error("fixture gate was not released");
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
}
emit({
  type: "result",
  subtype: budget ? "error_max_budget_usd" : mode === "error" ? "error" : "success",
  is_error: budget || mode === "error",
  result: mode === "error" ? "fixture failure" : "result",
  total_cost_usd: 0.125,
  usage: {
    input_tokens: 100,
    cache_read_input_tokens: 200,
    cache_creation_input_tokens: 300,
    output_tokens: 25,
  },
  modelUsage: { fixture: { contextWindow: 200000, maxOutputTokens: 64000 } },
});
