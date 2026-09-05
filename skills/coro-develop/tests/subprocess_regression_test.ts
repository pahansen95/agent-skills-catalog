import assert from "node:assert/strict";
import { SubprocessRunner } from "../scripts/coroutine.ts";

function options(stdinPayload = "") {
  return { cwd: Deno.cwd(), env: Deno.env.toObject(), stdinPayload };
}
Deno.test("consumer cancellation reaps child without waiting for its normal completion", async () => {
  let stoppedAt = 0;
  for await (
    const _event of new SubprocessRunner().runStreamJson([
      Deno.execPath(),
      "eval",
      "console.log(JSON.stringify({ready:true})); await new Promise(r=>setTimeout(r,4000));",
    ], options())
  ) {
    stoppedAt = performance.now();
    break;
  }
  assert(stoppedAt > 0);
  assert(performance.now() - stoppedAt < 2000, "abandoned child was not terminated promptly");
});
Deno.test("early child exit cleans up a large pending stdin payload", async () => {
  const events = [];
  for await (
    const e of new SubprocessRunner().runStreamJson(
      [Deno.execPath(), "eval", "Deno.exit(0)"],
      options("x".repeat(4_000_000)),
    )
  ) events.push(e);
  assert.deepEqual(events, []);
});
Deno.test("stream decoding handles split Unicode, malformed lines and final unterminated JSON", async () => {
  const code =
    'const data=new TextEncoder().encode(\'junk\\n{"text":"résumé 🧪"}\\n\\n{"tail":true}\');for(let i=0;i<data.length;i++)await Deno.stdout.write(data.subarray(i,i+1));';
  const events = [];
  for await (
    const e of new SubprocessRunner().runStreamJson(
      [Deno.execPath(), "eval", code],
      options(),
    )
  ) events.push(e);
  assert.deepEqual(events, [{ text: "résumé 🧪" }, { tail: true }]);
});

Deno.test("nonzero subprocess exit retains events and bounds its stderr diagnostic", async () => {
  const messages: string[] = [];
  const original = console.error;
  console.error = (...args: unknown[]) => messages.push(args.map(String).join(" "));
  const events = [];
  try {
    for await (
      const event of new SubprocessRunner().runStreamJson([
        Deno.execPath(),
        "eval",
        'console.log(JSON.stringify({partial:true}));console.error("fixture-failure "+"x".repeat(100000));Deno.exit(7);',
      ], options())
    ) events.push(event);
  } finally {
    console.error = original;
  }
  assert.deepEqual(events, [{ partial: true }]);
  assert.equal(messages.length, 1);
  assert.match(messages[0], /claude exited with code 7: fixture-failure/);
  assert(messages[0].length < 700);
});
