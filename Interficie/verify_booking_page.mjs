import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(here, "reserva_web.html"), "utf8");

const expectations = [
  ["#guestName field", /id="guestName"[^>]*type="text"/],
  ["#guestEmail field", /id="guestEmail"[^>]*type="email"/],
  ["#depositType field", /id="depositType"/],
  ["guest_name stored on reservation", /guest_name:\s*state\.guestName/],
  ["guest_email stored on reservation", /guest_email:\s*state\.guestEmail/],
  ["deposit_type stored on reservation", /deposit_type:\s*state\.depositType/],
  ["deposit_type passed to rules row", /deposit_type:\s*state\.depositType/],
  ["form validity checked before confirmation", /reportValidity\(\)/],
  ["confirmation email endpoint called", /\/api\/booking-confirmation-email/],
  ["dashboard button removed from confirmation", /id=\"openDashboardButton\"/],
];

const missing = expectations
  .filter(([label, pattern]) => label === "dashboard button removed from confirmation" ? pattern.test(html) : !pattern.test(html))
  .map(([label]) => label);

if (missing.length) {
  throw new Error(`Booking-page contract failed: ${missing.join(", ")}`);
}

console.log(JSON.stringify({ checked: expectations.length, status: "ok" }, null, 2));
