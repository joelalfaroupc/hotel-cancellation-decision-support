import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

const dashboardUrl = new URL("./index.html", import.meta.url).href;
const outputDir = fileURLToPath(new URL("./", import.meta.url));

const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("console", (msg) => {
  if (msg.type() === "error") errors.push(msg.text());
});
page.on("pageerror", (error) => errors.push(error.message));

await page.goto(dashboardUrl, { waitUntil: "networkidle" });
await page.screenshot({ path: `${outputDir}/dashboard_preview.png`, fullPage: true });
await page.locator("#reservationRows tr").first().click();
await page.screenshot({ path: `${outputDir}/dashboard_detail_preview.png`, fullPage: false });
await page.locator("[data-action-option]").first().click();
await page.locator("[data-execute]").click();

const result = {
  title: await page.title(),
  total: await page.locator("#totalBookings").textContent(),
  rows: await page.locator("#reservationRows tr").count(),
  drawerOpen: await page.locator("#detailDrawer.open").count(),
  executedVisible: await page.getByText("Ejecutada").count(),
  scheduledDots: await page.locator(".task-dot").count(),
  errors,
};

console.log(JSON.stringify(result, null, 2));
await browser.close();
