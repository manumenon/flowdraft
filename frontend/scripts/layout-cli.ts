#!/usr/bin/env node
/**
 * Layout CLI
 *
 * Node-callable entry point into the real TypeScript layout engine
 * (`src/workers/layoutCore.ts`'s `computeLayout` — plain, in-process elkjs,
 * no Worker/DOM involved), for non-browser callers. Today that's
 * `backend/app/services/ts_layout_bridge.py`, which invokes the bundled
 * output of this file (`dist-cli/layout-cli.cjs`, built via
 * `npm run build:layout-cli`) as a subprocess — the same
 * Python-calls-Node-subprocess-over-stdio pattern already established by
 * `scripts/flowdraft/elk_bridge.js`.
 *
 * Contract (mirrors elk_bridge.js's stdin/stdout shape, and layout.worker.ts's
 * own postMessage result shape):
 *   stdin:  JSON `LayoutRequest` — { elements, connections, title?,
 *           layoutDirection?, layoutAlgorithm? }
 *   stdout: JSON `{ success: true, graph }` on success, or
 *           `{ success: false, error }` on failure (also a non-zero exit
 *           code on failure, so subprocess callers can branch on returncode
 *           without parsing stdout first).
 */
import { computeLayout } from '../src/workers/layoutCore';
import type { LayoutRequest } from '../src/workers/layoutCore';

function readStdin(): Promise<string> {
  return new Promise((resolve, reject) => {
    let input = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => {
      input += chunk;
    });
    process.stdin.on('end', () => resolve(input));
    process.stdin.on('error', reject);
  });
}

async function main(): Promise<void> {
  const input = await readStdin();

  let request: LayoutRequest;
  try {
    request = JSON.parse(input);
  } catch (err: any) {
    process.stdout.write(JSON.stringify({ success: false, error: `Invalid JSON on stdin: ${err.message}` }));
    process.exitCode = 1;
    return;
  }

  try {
    const graph = await computeLayout(request);
    process.stdout.write(JSON.stringify({ success: true, graph }));
  } catch (err: any) {
    process.stdout.write(JSON.stringify({ success: false, error: err?.message || String(err) }));
    process.exitCode = 1;
  }
}

main().catch((err: any) => {
  // Should be unreachable (main() catches its own errors) — last-resort
  // guard so a truly unexpected throw still yields the same JSON contract
  // instead of an uncaught-exception stack trace on stderr and a bare
  // non-JSON stdout the Python bridge can't parse.
  process.stdout.write(JSON.stringify({ success: false, error: err?.message || String(err) }));
  process.exitCode = 1;
});
