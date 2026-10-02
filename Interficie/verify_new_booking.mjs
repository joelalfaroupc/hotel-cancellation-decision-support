import { chromium } from "playwright";

const dashboardUrl = new URL("./index.html", import.meta.url).href;

const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1365, height: 900 } });
const errors = [];
page.on("console", (msg) => {
  if (msg.type() === "error") errors.push(msg.text());
});
page.on("pageerror", (error) => errors.push(error.message));

await page.goto(dashboardUrl, { waitUntil: "networkidle" });
const drawerClosedBefore = await page.locator("#newReservationDrawer.open").count();
const monthOptions = await page.locator("#calendarMonth option").count();
await page.locator("#newReservationToggle").click();
await page.waitForTimeout(300);
const drawerOpenAfterClick = await page.locator("#newReservationDrawer.open").count();
await page.locator("button.compact").click();
await page.waitForTimeout(1000);

const result = {
  drawerClosedBefore,
  drawerOpenAfterClick,
  monthOptions,
  newBookingResult: await page.locator("#newBookingResult").textContent(),
  drawerOpen: await page.locator("#detailDrawer.open").count(),
  rows: await page.locator("#reservationRows tr").count(),
  errors,
};

console.log(JSON.stringify(result, null, 2));
await browser.close();
