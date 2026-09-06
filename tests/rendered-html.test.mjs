import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server returns the education admin app shell", async () => {
  const response = await render();

  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /教育内容中台/);
  assert.match(html, /zh-CN/);
});

test("page reads and writes workspace data through the platform API adapter", async () => {
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  const api = await readFile(new URL("../app/lib/platform-api.ts", import.meta.url), "utf8");

  assert.match(page, /localPlatformApi\.loadWorkspace\(\)/);
  assert.match(page, /localPlatformApi\.saveWorkspace\(/);
  assert.match(page, /localPlatformApi\.createSource\(/);
  assert.match(page, /listBackendSources\(\)/);
  assert.match(page, /createBackendSource\(/);
  assert.match(page, /updateBackendSource\(/);
  assert.match(page, /listBackendTasks\(\)/);
  assert.match(page, /createBackendTask\(/);
  assert.match(page, /updateBackendTask\(/);
  assert.match(page, /executeBackendTask\(/);
  assert.match(page, /processBackendMaterial\(/);
  assert.match(page, /searchBackendMaterials\(/);
  assert.match(page, /getHotThresholds\(/);
  assert.match(page, /putHotThresholds\(/);
  assert.match(page, /点赞 \/ 收藏门槛/);
  assert.match(page, /保存门槛/);
  assert.match(page, /buildChangzhouNewsPrompt/);
  assert.match(page, /内容提示/);
  assert.match(page, /升学规划相关性/);
  assert.match(page, /全国高校招生/);
  assert.match(page, /访问密码/);
  assert.match(api, /X-App-Password/);
  assert.match(page, /localPlatformApi\.createTask\(/);
  assert.match(page, /localPlatformApi\.createDocument\(/);
  assert.match(api, /export type PlatformApi/);
  assert.match(api, /export const localPlatformApi/);
});
