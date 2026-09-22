// 全站 JS 语法验证：把每个自建脚本文件与每段内联 <script> 用 new Function 解析。
// 解析失败即报错退出（fast-fail），保证旧 WebView 不会再遇到任何解析错误。
const fs = require("fs");
const path = require("path");

const ROOT = "/data/code/AIagent/skills/knowledge-site/technical-knowledge";

const jsFiles = [
  "site/nav.js", "site/shell.js", "site/i18n.js", "site/matrix.js",
  "site/matrix-view.js", "site/panorama-data.js", "site/panorama-view.js",
  "site/project-links.js", "site/project-status.js", "site/projects-page.js",
  "site/sources.js",
];

const htmlFiles = [
  "index.html", "papers/index.html", "sources/index.html", "projects/index.html",
  "apps/agent-evaluation/index.html", "apps/learning/index.html",
  "apps/learning/history.html", "apps/learning/intuition.html",
  "apps/learning/openmaic.html", "apps/learning/transfer.html",
];

let failed = 0;

for (const rel of jsFiles) {
  const src = fs.readFileSync(path.join(ROOT, rel), "utf-8");
  try {
    new Function(src);
    console.log("OK  ", rel);
  } catch (err) {
    failed++;
    console.log("FAIL", rel, "-", err.message);
  }
}

for (const rel of htmlFiles) {
  const html = fs.readFileSync(path.join(ROOT, rel), "utf-8");
  const blocks = [...html.matchAll(/<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/g)];
  blocks.forEach((m, i) => {
    const code = m[1].trim();
    if (!code) return;
    try {
      new Function(code);
      console.log("OK  ", rel + "#block" + (i + 1));
    } catch (err) {
      failed++;
      console.log("FAIL", rel + "#block" + (i + 1), "-", err.message);
    }
  });
}

if (failed > 0) {
  console.log("TOTAL FAILED:", failed);
  process.exit(1);
}
console.log("ALL PASS");
