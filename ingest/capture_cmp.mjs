// Capture actual CMP content instead of guessing a Markdown URL for every route.
// Usage: node ingest/capture_cmp.mjs routes.json captured.json
import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
const require = createRequire(new URL("../web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");
const [input, output] = process.argv.slice(2);
const routes = JSON.parse(readFileSync(input, "utf8"));
const browser = await chromium.launch({ headless: true });
const captured = {};
let cursor = 0;
function routePath(route) {
  if (["basic", "ui", "module", "v5", "native"].includes(route)) return `/component/${route}`;
  if (["m3inH5", "H5inApp", "wechatInH5"].includes(route)) return `/third/${route}`;
  if (route === "iosIntercept") return "/fingerpost/fingerpost/iosIntercept";
  return "/" + route.replace(/^\//, "");
}
try {
  await Promise.all(Array.from({ length: 3 }, async () => {
    const page = await browser.newPage();
    // Download actions use window.open rather than anchor hrefs. Record the URL
    // by clicking in an intercepted window.open, without following downloads.
    await page.addInitScript(() => { window.open = (url) => { window.__capturedURL = String(url); return null; }; });
    while (cursor < routes.length) {
      const route = routes[cursor++];
      const sources = new Set();
      const track = response => {
        if (response.ok() && /\/iframePhone\/(?:md\/|source\/|api\/)|iosIntercept\.html/.test(response.url())) sources.add(response.url());
      };
      page.on("response", track);
      try {
        await page.goto("https://open.seeyoncloud.com/cmpdev/#" + routePath(route), { waitUntil: "networkidle", timeout: 45000 });
        // Expand nested API parameter rows so exported tables include all fields.
        for (let depth = 0; depth < 8; depth++) {
          const toggles = page.locator('.el-table__expand-icon:not(.el-table__expand-icon--expanded)');
          const n = await toggles.count();
          if (!n) break;
          for (let i = n - 1; i >= 0; i--) await toggles.nth(i).click({ timeout: 2000 }).catch(() => {});
        }
        for (const button of (await page.locator('.resource-actions button').all()).reverse()) {
          await page.evaluate(() => { window.__capturedURL = null; });
          await button.click();
          const url = await page.evaluate(() => window.__capturedURL);
          if (url) await button.evaluate((el, href) => { const a = document.createElement('a'); a.href = href; a.textContent = el.textContent; el.replaceWith(a); }, url);
        }
        let html;
        const iframe = page.frames().find(f => /\/(?:iosIntercept|cmp-icon|api)\.html/.test(f.url()));
        if (iframe) {
          await iframe.locator('body').waitFor();
          await iframe.waitForFunction(() => document.body.innerText.trim().length > 80, null, { timeout: 15000 });
          sources.add(iframe.url());
          html = await iframe.locator('body').evaluate(el => {
            const copy = el.cloneNode(true);
            copy.querySelectorAll('[src], a[href]').forEach(n => { const attr = n.hasAttribute('src') ? 'src' : 'href'; n.setAttribute(attr, new URL(n.getAttribute(attr), document.baseURI).href); });
            return copy.innerHTML;
          });
        } else {
          const main = page.locator('.el-main').last();
          await main.waitFor();
          await page.waitForFunction(() => (document.querySelector('.el-main:last-child')?.innerText || '').trim().length > 80, null, { timeout: 15000 }).catch(() => {});
          html = await main.evaluate(el => {
            const copy = el.cloneNode(true);
            copy.querySelectorAll('.main-right, .el-backtop, .el-loading-mask, .code-toolbar button, .code-panel-header button').forEach(n => n.remove());
            copy.querySelectorAll('pre:not(:has(code))').forEach(pre => { const code = document.createElement('code'); code.textContent = pre.textContent; pre.replaceChildren(code); });
            copy.querySelectorAll('[src], a[href]').forEach(n => { const attr = n.hasAttribute('src') ? 'src' : 'href'; n.setAttribute(attr, new URL(n.getAttribute(attr), document.baseURI).href); });
            return copy.innerHTML;
          });
        }
        captured[route] = { url: page.url(), html, sources: [...sources] };
        writeFileSync(output, JSON.stringify(captured, null, 2));
        console.log(`captured ${route}: ${html.length}`);
      } catch (e) { console.error(`FAILED ${route}: ${e.message}`); }
      finally { page.off('response', track); }
    }
    await page.close();
  }));
} finally { await browser.close(); }
