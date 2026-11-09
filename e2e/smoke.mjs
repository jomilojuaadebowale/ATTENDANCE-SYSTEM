// Manual end-to-end smoke test: real browser -> Next.js -> FastAPI -> PostgreSQL.
// Prereqs: API on :8000 (AUTH_PROVIDER=dev, seeded), web on :3000. Run: node e2e/smoke.mjs
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(here, "../apps/web/package.json"));
const jsQR = require("jsqr");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE ?? "playwright");

const WEB = process.env.WEB_URL ?? "http://localhost:3000";
const SHOTS = process.env.SHOTS_DIR ?? "/tmp";
const HALL = { latitude: 7.5186, longitude: 4.5213, accuracy: 10 };
let step = 0;
const ok = (msg) => console.log(`  ✓ ${++step}. ${msg}`);

const browser = await chromium.launch();
async function person(email, geo = HALL) {
  const ctx = await browser.newContext({ geolocation: geo, permissions: ["geolocation"], viewport: { width: 1100, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(`${WEB}/login`);
  await page.getByLabel("University email").fill(email);
  await page.getByRole("button", { name: "Sign in" }).click();
  return { ctx, page };
}

async function readQrFromCanvas(page) {
  const canvas = page.locator('canvas[aria-label="Attendance QR code"]');
  await canvas.waitFor({ state: "visible", timeout: 15000 });
  await page.waitForTimeout(800);
  const img = await canvas.evaluate((c) => {
    const d = c.getContext("2d").getImageData(0, 0, c.width, c.height);
    return { w: d.width, h: d.height, data: Array.from(d.data) };
  });
  const code = jsQR(Uint8ClampedArray.from(img.data), img.w, img.h);
  if (!code) throw new Error("Could not decode the QR code rendered on the lecturer screen");
  return code.data;
}

async function studentScan(page, payload) {
  await page.goto(`${WEB}/student/scan`);
  await page.getByLabel("QR code text").fill(payload);
  await page.getByRole("button", { name: "Use code" }).click();
}

console.log("Lecturer opens a session");
const lec = await person("lecturer1@example.edu");
await lec.page.waitForURL("**/lecturer");
ok("lecturer signs in and lands on /lecturer");
await lec.page.goto(`${WEB}/lecturer/sessions/new`);
await lec.page.getByLabel("Course").selectOption({ label: "CSC 308 — Numerical Computation" });
await lec.page.getByLabel("Lecture venue").selectOption({ label: "Demo Lecture Theatre 1 (75 m)" });
await lec.page.getByRole("button", { name: "Start session" }).click();
await lec.page.waitForURL(/\/lecturer\/sessions\/[0-9a-f-]{36}/);
const sessionUrl = lec.page.url();
ok(`session created: ${sessionUrl.split("/").pop()}`);
const qr1 = await readQrFromCanvas(lec.page);
if (!/^v1\.[0-9a-f-]{36}\.\d+\.[\w-]{22}$/.test(qr1)) throw new Error(`Unexpected QR payload: ${qr1}`);
ok("QR code rendered on screen and decodes with jsQR");
await lec.page.screenshot({ path: `${SHOTS}/e2e-lecturer-session.png` });

console.log("Students scan");
const s1 = await person("student1@example.edu");
await s1.page.waitForURL("**/student");
await studentScan(s1.page, await readQrFromCanvas(lec.page));
await s1.page.getByText("Attendance recorded", { exact: true }).waitFor({ timeout: 15000 });
ok("student 1 (at the venue) -> 'Attendance recorded' (confirmed by the server)");
await s1.page.screenshot({ path: `${SHOTS}/e2e-student-recorded.png` });

await studentScan(s1.page, await readQrFromCanvas(lec.page));
await s1.page.getByText("Already recorded", { exact: true }).waitFor({ timeout: 15000 });
ok("student 1 scanning again -> 'Already recorded' (no duplicate)");

const far = { latitude: HALL.latitude + 0.003, longitude: HALL.longitude, accuracy: 10 };
const s2 = await person("student2@example.edu", far);
await s2.page.waitForURL("**/student");
await studentScan(s2.page, await readQrFromCanvas(lec.page));
await s2.page.getByText("Not recorded", { exact: true }).waitFor({ timeout: 15000 });
await s2.page.getByText(/limit 75 m/).waitFor();
ok("student 2 (~330 m away) -> 'Not recorded', outside the geofence");

const s3 = await person("student3@example.edu");
await s3.page.waitForURL("**/student");
await studentScan(s3.page, "https://example.com/not-attendance");
await s3.page.getByText("Not an attendance code").waitFor();
ok("student 3 scanning a random QR -> 'Not an attendance code'");
await studentScan(s3.page, await readQrFromCanvas(lec.page));
await s3.page.getByText("Attendance recorded", { exact: true }).waitFor({ timeout: 15000 });
ok("student 3 -> 'Attendance recorded'");

console.log("Lecturer reviews and finalizes");
await lec.page.reload();
await lec.page.getByRole("row", { name: /CSC\/2022\/001/ }).getByText("Verified").waitFor({ timeout: 15000 });
await lec.page.getByRole("row", { name: /CSC\/2022\/002/ }).getByText("Not Marked").waitFor();
ok("roster shows student 1 verified and student 2 'not marked' (not 'absent' while open)");
await lec.page.getByLabel("Select Demo Student 02").check();
await lec.page.getByLabel("Reason").selectOption("no_phone");
await lec.page.getByRole("button", { name: /Mark 1 selected present/ }).click();
await lec.page.getByText(/Marked 1 present/).waitFor();
await lec.page.getByRole("row", { name: /CSC\/2022\/002/ }).getByText("Manual").waitFor();
ok("lecturer marks student 2 manually (reason: no phone)");
await lec.page.getByRole("button", { name: "Close session" }).click();
await lec.page.getByText("Session closed and finalized.").waitFor();
ok("lecturer closes (finalizes) the session");
await lec.page.screenshot({ path: `${SHOTS}/e2e-lecturer-closed.png` });

console.log("Reports");
await s1.page.goto(`${WEB}/student`);
await s1.page.getByText("100.0%").first().waitFor({ timeout: 15000 });
ok("student 1 dashboard shows 100.0% for CSC 308 (database-backed)");
await s2.page.goto(`${WEB}/student/history`);
await s2.page.getByText("Marked by lecturer").waitFor();
ok("student 2 history shows 'Marked by lecturer'");
await lec.page.goto(`${WEB}/lecturer`);
await lec.page.getByRole("link", { name: "Report" }).first().click();
await lec.page.getByText("CSC 308 attendance report").waitFor();
const [download] = await Promise.all([lec.page.waitForEvent("download"), lec.page.getByRole("button", { name: /Export CSV/ }).click()]);
ok(`lecturer exports CSV: ${download.suggestedFilename()}`);
await lec.page.screenshot({ path: `${SHOTS}/e2e-report.png` });

console.log("Permissions");
await s1.page.goto(`${WEB}/admin`);
await s1.page.getByText("not available for your account").waitFor();
ok("student visiting /admin is turned away (and redirected home)");
const adm = await person("admin@example.edu");
await adm.page.waitForURL("**/admin");
await adm.page.getByText("System overview").waitFor();
await adm.page.getByText("Audit events (7 days)").waitFor();
ok("admin sees the overview");
await adm.page.goto(`${WEB}/admin/audit`);
await adm.page.getByText("attendance.manual_mark").first().waitFor();
ok("audit log contains the manual-mark event");
await adm.page.screenshot({ path: `${SHOTS}/e2e-admin-audit.png` });

await browser.close();
console.log(`\nAll ${step} end-to-end checks passed.`);
