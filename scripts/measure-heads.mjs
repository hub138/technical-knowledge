// 量各页面头部几何，输出 JSON。由 scripts/consistency_audit.py 调用。
//
// 用 CDP 而不是 `chrome --dump-dom`：后者在解析完就快照，而首页的 hero 是
// JS 渲染的（要等 /api/notes 回来才有），快照里选择器全是 null。
// CDP 可以自己决定"等多久、等什么"，读到的才是读者看到的那一版。
//
// 用法: node measure-heads.mjs '<json pages>' '<out path>'
import CP from 'node:child_process';
import http from 'node:http';
import path from 'node:path';
import fs from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const WebSocket = require(
  '/Users/leoqqian/.nvm/versions/node/v18.20.8/lib/node_modules/browser-sync/node_modules/ws'
);

const CHROME = path.join(
  process.env.HOME,
  '.cache/puppeteer/chrome-headless-shell/mac_arm-142.0.7444.175/chrome-headless-shell-mac-arm64/chrome-headless-shell'
);
const PORT = 9861;
const pages = JSON.parse(process.argv[2]);
const outPath = process.argv[3];

const child = CP.spawn(
  CHROME,
  ['--headless', '--disable-gpu', `--remote-debugging-port=${PORT}`, '--window-size=1440,1000', 'about:blank'],
  { stdio: 'ignore' }
);
const get = (p) =>
  new Promise((res, rej) => {
    const r = http.request(
      { host: '127.0.0.1', port: PORT, path: p, method: p.startsWith('/json/new') ? 'PUT' : 'GET' },
      (x) => { let d = ''; x.on('data', (c) => (d += c)); x.on('end', () => res(JSON.parse(d))); }
    );
    r.on('error', rej);
    r.end();
  });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let ws;
const result = {};
try {
  for (let i = 0; i < 60; i++) { try { await get('/json/version'); break; } catch { await sleep(200); } }
  const t = await get('/json/new?about:blank');
  ws = new WebSocket(t.webSocketDebuggerUrl, { maxPayload: 32 * 1024 * 1024 });
  let id = 0;
  const pending = new Map();
  const send = (m, p = {}) =>
    new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method: m, params: p })); });
  ws.on('message', (m) => {
    const d = JSON.parse(m);
    if (d.id && pending.has(d.id)) { pending.get(d.id)(d.result || d.error); pending.delete(d.id); }
  });
  await new Promise((r) => ws.on('open', r));
  await send('Page.enable');
  await send('Runtime.enable');

  for (const [name, url] of pages) {
    await send('Page.navigate', { url });
    // 等 hero 出现且真的有高度（首页是 JS 渲染的，要等数据）
    let ok = false;
    for (let i = 0; i < 30; i++) {
      await sleep(800);
      const r = await send('Runtime.evaluate', {
        returnByValue: true,
        expression: '!!(document.querySelector(".hero") && document.querySelector(".hero").getBoundingClientRect().height > 0)',
      });
      if (r?.result?.value) { ok = true; break; }
    }
    if (!ok) { result[name] = { error: 'hero 未出现' }; continue; }

    const r = await send('Runtime.evaluate', {
      returnByValue: true,
      expression: `(function(){
        function geom(sel){
          var el = document.querySelector(sel);
          if(!el) return null;
          var b = el.getBoundingClientRect(), cs = getComputedStyle(el);
          return {
            top: Math.round(b.top),
            fs: Math.round(parseFloat(cs.fontSize)),
            fw: +cs.fontWeight,
            mb: Math.round(parseFloat(cs.marginBottom) || 0)
          };
        }
        var hero = document.querySelector('.hero');
        var shell = document.querySelector('.tk-shell') || document.querySelector('app');
        var hcs = getComputedStyle(hero);
        var scs = shell ? getComputedStyle(shell) : null;
        return JSON.stringify({
          title: geom('.hero h1') || geom('h1'),
          heroPad: { top: Math.round(parseFloat(hcs.paddingTop)||0),
                     bottom: Math.round(parseFloat(hcs.paddingBottom)||0) },
          shellPad: scs ? { top: Math.round(parseFloat(scs.paddingTop)||0),
                            left: Math.round(parseFloat(scs.paddingLeft)||0) } : null
        });
      })()`,
    });
    result[name] = JSON.parse(r?.result?.value || '{}');
  }
} catch (e) {
  result.__error = e.message;
} finally {
  if (ws) ws.close();
  child.kill();
  fs.writeFileSync(outPath, JSON.stringify(result, null, 2), 'utf-8');
}
