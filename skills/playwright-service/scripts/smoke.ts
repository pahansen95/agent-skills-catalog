/**
 * Smoke test for the shared playwright-dev-server service: connect via the
 * unix socket, evaluate in a real page, close. Exit 0 iff healthy.
 *
 * Usage: deno run --allow-all smoke.ts
 */
import { chromium } from "npm:playwright-core@1.62.1";

const endpoint =
  "ws+unix:///Volumes/Dev/Machines/localhost/Services/playwright-dev-server/run/playwright-dev-server.sock:/";

try {
  const browser = await chromium.connect(endpoint, { timeout: 30_000 });
  try {
    const page = await browser.newPage();
    const result = await page.evaluate("6 * 7");
    if (result !== 42) throw new Error(`evaluate returned ${result}`);
    console.log(`ok: service healthy via unix socket (chromium ${browser.version()})`);
  } finally {
    await browser.close();
  }
  Deno.exit(0);
} catch (err) {
  console.error(`FAIL: ${err instanceof Error ? err.message.split("\n")[0] : err}`);
  console.error("triage: see SKILL.md — Verify / triage");
  Deno.exit(1);
}
