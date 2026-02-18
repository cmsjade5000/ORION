#!/usr/bin/env node
/**
 * Minimal Coinbase Exchange WS ticker fetcher (public).
 *
 * Prints one JSON line to stdout:
 *   {"venue":"coinbase_ws","product":"BTC-USD","price":67500.12,"ts_ms":...}
 *
 * Exits non-zero on failure/timeout.
 */

const { setTimeout: sleep } = require("timers/promises");

function usage() {
  console.error("Usage: node scripts/arb/coinbase_ws_price.js <PRODUCT_ID> [timeout_ms]");
  process.exit(2);
}

async function main() {
  const product = process.argv[2];
  const timeoutMs = Number(process.argv[3] ?? "1500");
  if (!product) usage();

  const url = "wss://ws-feed.exchange.coinbase.com";
  const ws = new WebSocket(url);

  let done = false;
  let timer = null;

  function finish(code, obj, errMsg) {
    if (done) return;
    done = true;
    try { if (timer) clearTimeout(timer); } catch {}
    try { ws.close(); } catch {}
    if (obj) {
      process.stdout.write(JSON.stringify(obj) + "\n");
      process.exit(0);
    }
    if (errMsg) process.stderr.write(errMsg + "\n");
    process.exit(code);
  }

  timer = setTimeout(() => finish(1, null, "WS_TIMEOUT"), Math.max(200, timeoutMs));

  ws.addEventListener("open", () => {
    const sub = {
      type: "subscribe",
      product_ids: [String(product)],
      channels: ["ticker"],
    };
    ws.send(JSON.stringify(sub));
  });

  ws.addEventListener("message", (ev) => {
    try {
      const msg = JSON.parse(String(ev.data ?? ""));
      if (!msg || msg.type !== "ticker") return;
      if (msg.product_id !== product) return;
      const price = Number(msg.price);
      if (!Number.isFinite(price) || price <= 0) return;
      finish(0, { venue: "coinbase_ws", product, price, ts_ms: Date.now() }, null);
    } catch {
      // ignore parse errors
    }
  });

  ws.addEventListener("error", (e) => {
    finish(1, null, "WS_ERROR");
  });

  // Some environments require a brief delay to let the WS open before the timeout.
  await sleep(0);
}

main().catch((e) => {
  process.stderr.write(String(e && e.stack ? e.stack : e) + "\n");
  process.exit(1);
});

