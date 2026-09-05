---
name: playwright-service
description: Use the machine's shared Playwright server for browser automation and web testing. Connect to the running service instead of launching browsers in-process or installing anything. Covers endpoints, the required client pin, engine support, hygiene, and triage.
metadata:
  version: "1.0.0"
  service-label: "io.peterhansen.playwright-dev-server"
  playwright-pin: "1.62.1"
---

# playwright-service — shared browser automation

A Playwright server runs on this machine as an always-on user service. When you need a real
browser — scraping, webapp testing, screenshots, ad-hoc page automation — connect to it.
Do NOT launch browsers in-process, `playwright install` anything, or spawn your own server.

## Connect

Hard constraint: the client MUST be `playwright-core@1.62.1`. The wire protocol is
version-coupled; other versions are rejected or misbehave.

Preferred endpoint (unix socket, auth = file permissions):

```ts
import { chromium } from "npm:playwright-core@1.62.1";

const browser = await chromium.connect(
  "ws+unix:///Volumes/Dev/Machines/localhost/Services/playwright-dev-server/run/playwright-dev-server.sock:/",
);
const page = await browser.newPage();
await page.goto("https://example.com");
// ... work ...
await browser.close(); // ALWAYS — see hygiene
```

Fallback endpoint (TCP, for clients whose WebSocket stack lacks `ws+unix`):

```
ws://127.0.0.1:4445/
```

`firefox` works identically. Launch options are client-chosen per connection —
`chromium.connect(endpoint)` then `browser.newPage()` gives a fresh context; for custom
launch options connect carries them implicitly (headed browsers work — the service runs in
the GUI session). Unsafe launch options (executablePath, raw args) are filtered server-side.

## Engine support

| Engine | Status |
| --- | --- |
| chromium | healthy |
| firefox | healthy |
| webkit | UNUSABLE on this host — do not retry, do not debug |

webkit: macOS 14 gets a frozen webkit build (2251) under this pin, and the driver sends a
`Page.overrideSetting` that build does not know. Every `newPage` fails; via the server it
hangs. This is upstream, documented, and waits on macOS 15 or a pin bump.

## Hygiene

- `await browser.close()` when done — every connection may own a real browser process;
  disconnect tears down everything you created server-side, but close promptly anyway.
- The service gates at 16 concurrent connections shared across all consumers. Don't hold
  idle connections; connect, work, close.
- Contexts are the isolation unit. One `connect` + many `newContext()`/`newPage()` beats
  many connections.

## Verify / triage

Liveness (either transport):

```sh
curl -s --unix-socket /Volumes/Dev/Machines/localhost/Services/playwright-dev-server/run/playwright-dev-server.sock http://localhost/json
curl -s http://127.0.0.1:4445/json
```

Deep probe (from the project checkout, e.g. `space/playwright-dev-server` in the dev-tools
view): `deno task health` — probes chromium+firefox over both transports; 60s deadline per
probe.

Smoke script in this skill: `deno run --allow-all scripts/smoke.ts` (connects, evaluates,
closes; exits non-zero on failure). The skill directory carries its own `deno.json` so the
snippet's npm resolution works regardless of ambient package.json/deno.json config.

If the service is down: it is `io.peterhansen.playwright-dev-server`, supervised by the
user-service manager (`launchctl print gui/$(id -u)/io.peterhansen.playwright-dev-server`);
logs at `/Volumes/Dev/Machines/localhost/Services/playwright-dev-server/logs/`. The service
definition lives in the mac-studio machine repo under `Services/playwright-dev-server/`
(operations, upgrade, rollback documented there). Report the outage; do not fall back to
ad-hoc browser spawning.
