/**
 * A browser walk through the whole app, asserting the things a unit test
 * cannot: that onboarding completes, that switching language switches
 * everything, that a lesson plays, and that the honest messages actually
 * reach the screen.
 *
 * Needs a *freshly started backend with an empty database*, because it starts
 * from first run:
 *
 *   rm -rf /tmp/hanbat-smoke && mkdir -p /tmp/hanbat-smoke
 *   HANBAT_DATA_DIR=/tmp/hanbat-smoke HANBAT_DB=/tmp/hanbat-smoke/app.sqlite3 \
 *     python3 -m uvicorn app.main:app --port 8756 &
 *   cd frontend && npm run build && npm i --no-save playwright && node ui-smoke.mjs
 *
 * Screenshots land in ./ui-smoke-shots for eyeballing.
 */

import { chromium } from "playwright";
import fs from "node:fs";

const BASE = "http://127.0.0.1:8756";
const shots = process.env.SHOTS ?? "./ui-smoke-shots";
fs.mkdirSync(shots, { recursive: true });

const errors = [];
// The sandbox ships a Chromium build whose revision does not match this
// Playwright version's default, so point at it explicitly rather than
// downloading another copy.
let crashed = "";
const browser = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
  args: ["--no-sandbox"],
});
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error") errors.push(`console: ${m.text()}`); });

const results = [];
const check = (label, cond, detail = "") =>
  results.push({ label, cond: !!cond, detail });

/** Wait for text to appear.
 *
 * Navigation inside the app is client-side, so `waitForLoadState` returns
 * immediately and proves nothing — the fetch has not been issued yet, let
 * alone rendered. Every content assertion has to wait on the element itself.
 */
async function sees(text, timeout = 8000) {
  try {
    await page.getByText(text).first().waitFor({ state: "visible", timeout });
    return true;
  } catch {
    return false;
  }
}

async function shot(name) {
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}

// ---- first run ----------------------------------------------------------
await page.goto(BASE, { waitUntil: "networkidle" });
check("redirects to onboarding", page.url().includes("/welcome"), page.url());
check("greeting is rendered", await sees("Four questions"));
await shot("01-welcome");

await page.getByRole("button", { name: /Start/ }).click({ timeout: 15000 });
check("language question", await sees("Which language do you want to learn?"));
await shot("02-language");

// Answer each question by clicking an option; the last one reveals Finish
// rather than auto-advancing, so the loop watches for it.
await page.getByRole("button", { name: /Mandarin Chinese/ }).click();
for (let i = 0; i < 4; i++) {
  const finish = page.getByRole("button", { name: /^Finish$/ });
  if (await finish.isVisible().catch(() => false)) {
    await finish.click();
    break;
  }
  const option = page.locator("h1 ~ div > button").first();
  if (!(await option.isVisible().catch(() => false))) break;
  await option.click();
  await page.waitForTimeout(250);
}
await page.waitForURL((u) => !u.pathname.startsWith("/welcome"), { timeout: 12000 });
await page.waitForLoadState("networkidle");
check("lands in the app", !page.url().includes("/welcome"), page.url());
await shot("03-dashboard-zh");

// ---- dashboard ----------------------------------------------------------
check("mandarin greeting", await sees("今天的中文"));
check("nav has Lessons", await page.getByRole("link", { name: "Lessons" }).first().isVisible());
check("no Conjugation tab for Mandarin",
  (await page.getByRole("link", { name: "Conjugation" }).count()) === 0);

// ---- lessons ------------------------------------------------------------
await page.getByRole("link", { name: "Lessons" }).first().click();
check("pinyin lessons listed", await sees("What pinyin is, and what it is not"));
check("later lessons are locked, with a reason", await sees(/Finish zh-pinyin-001 first/));
await shot("04-lessons-zh");

await page.getByText("What pinyin is, and what it is not").first().click();
check("lesson player opens", await sees(/Chinese is written in characters/));
await shot("05-lesson-zh");

// walk a few steps
for (let i = 0; i < 3; i++) {
  const next = page.getByRole("button", { name: /Continue/ });
  if (await next.isVisible().catch(() => false)) {
    await next.click();
    await page.waitForTimeout(350);
  }
}
await shot("06-lesson-step");

// ---- writing system -----------------------------------------------------
await page.goto(`${BASE}/writing`, { waitUntil: "networkidle" });
check("pinyin units render", await sees("Pinyin"));
await page.getByRole("tab", { name: /Chinese characters/ }).click();
check("hanzi is declared an open set, not a stalled bar", await sees(/An open set/));
check("and says its content is unwritten", await sees(/No content is authored for it yet/));
await shot("07-writing-zh");

// ---- switch to Korean ---------------------------------------------------
await page.goto(`${BASE}/languages`, { waitUntil: "networkidle" });
await shot("08-languages");
// Switch deliberately to Korean rather than "whichever is first", so the
// assertions below can name Korean content.
await page.locator("article").filter({ hasText: "Korean" })
  .getByRole("button", { name: /Switch to this/ }).click();
await page.waitForTimeout(900);
await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
check("switching changes the whole app", await sees("오늘의 한국어"));
await shot("09-dashboard-switched");

// ---- korean specifics ---------------------------------------------------
await page.goto(`${BASE}/pronunciation`, { waitUntil: "networkidle" });
await shot("10-pronunciation");
await page.goto(`${BASE}/grammar`, { waitUntil: "networkidle" });
check("korean grammar points listed", await sees(/이에요/));
check("conjugation tab appears for korean",
  (await page.getByRole("link", { name: "Conjugation" }).count()) > 0);
await shot("11-grammar");
await page.goto(`${BASE}/vocabulary`, { waitUntil: "networkidle" });
await shot("12-vocabulary");
await page.goto(`${BASE}/review`, { waitUntil: "networkidle" });
await shot("13-review");
await page.goto(`${BASE}/tutor`, { waitUntil: "networkidle" });
check("tutor is honest about no model", await sees("No model is running"));
await shot("14-tutor");
await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
check("settings lists network features", await sees("Allow network features"));
await shot("15-settings");
await page.goto(`${BASE}/progress`, { waitUntil: "networkidle" });
await shot("16-progress");
await page.goto(`${BASE}/practice`, { waitUntil: "networkidle" });
check("practice lists this language's own drills", await sees(/Predict the 받침 sound/));
await page.getByText("Read the letters").first().click();
check("a drill starts", await sees(/What sound does/));
await shot("17-practice");

// Make the same mistake repeatedly, the way a real learner would, so the
// adaptive engine has a pattern to find rather than a one-off slip.
await page.evaluate(async () => {
  for (let i = 0; i < 5; i++) {
    await fetch("/api/answer?lang=ko", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        correct: false, skill: "grammar", kind: "particle_choice",
        item_type: "grammar", item_id: "ko-g-002",
        expected: "\uc740", given: "\uc774",
      }),
    });
  }
});
// One careless slip: right before, answered fast, one character out. The
// diagnosis engine should file this separately from the five real gaps above.
await page.evaluate(async () => {
  const body = (correct, ms, given) => JSON.stringify({
    correct, skill: "vocabulary", kind: "recall", item_type: "vocab",
    item_id: "ko-v-0001", expected: "사람", given, response_ms: ms,
  });
  await fetch("/api/answer?lang=ko", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: body(true, 4000, "사람"),
  });
  await fetch("/api/answer?lang=ko", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: body(false, 900, "사람을"),
  });
});

await page.goto(`${BASE}/mistakes`, { waitUntil: "networkidle" });
check("mistakes are grouped by why they happened",
  await sees(/Grouped by why they happened/));
check("the real gaps are counted apart from the slips",
  await sees(/things to learn/));
check("careless slips are named and excluded on purpose",
  await sees(/not scheduled, on purpose/));
check("the grammar reason group is present", await sees(/^Grammar$/));
await page.getByText(/^Grammar$/).first().click();
check("expanding a reason shows the actual answers", await sees(/은/));
await shot("23-mistakes-by-reason");

// Five failures on one pair make it a weak point with a fix attached, so it is
// listed once — with the authored walkthrough folded into that fix rather than
// offered separately under a second heading.
check("the confusion pattern is offered", await sees(/은\/는 versus 이\/가/));
await page.locator(".card").filter({ hasText: "은/는 versus 이/가" })
  .getByRole("link").first().click();
check("the fix for a confusion drills the pair rather than a grammar point",
  await sees(/Tell them apart/));
await page.getByRole("button", { name: /The longer walkthrough/ }).click();
check("and the authored walkthrough is there, plain words first",
  await sees(/The one-line version/));
await shot("20-mini-course");
await page.goBack({ waitUntil: "networkidle" });

// ---- the same rule, failed enough times to become a pattern -------------
// Four failures on one Korean liaison word: the attributor should pin them to
// 연음, and the app should then offer a targeted fix rather than more of the
// same question.
await page.evaluate(async () => {
  for (const word of ["한국어", "꽃이", "옷이", "책을"]) {
    await fetch("/api/answer?lang=ko", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        correct: false, skill: "pronunciation", kind: "batchim_predict",
        expected: word, given: "", response_ms: 7000,
      }),
    });
  }
});

await page.goto(`${BASE}/mistakes`, { waitUntil: "networkidle" });
check("the specific rule is named, not just the skill",
  await sees(/What keeps going wrong/));
check("and it says how many times", await sees(/times · pronunciation/));
await shot("29-weak-points");

// Target the sound rule specifically: the same screen serves grammar points
// and confusion pairs, and each builds a different shape of fix.
await page.locator(".card").filter({ hasText: "연음" })
  .getByRole("link").first().click();
check("the fix opens with the plain-words explanation",
  await sees(/What the rule actually says/));
check("it names the rule in its own script", await sees(/연음/));
check("it shows what the learner actually wrote", await sees(/What you actually wrote/));
check("a sound rule is fixed by hearing and saying it",
  await sees(/Hear the difference/) && await sees(/Say it yourself/));
await shot("30-remediation");
await page.getByRole("button", { name: /Next: Hear the difference/ }).click();
check("the drill step runs a real exercise", await sees(/Which one did you hear/, 12000));
await shot("31-remediation-drill");

// ---- practise my own mistakes -------------------------------------------
await page.goto(`${BASE}/mistakes`, { waitUntil: "networkidle" });
await page.getByText(/^Pronunciation$/).first().click();
check("expanding a group says what to do about it",
  await sees(/pronunciation lab, then say the examples out loud/));
await page.getByRole("button", { name: /Practise these/ }).first().click();
check("practising mistakes uses the learner's own items",
  await sees(/Practising your mistakes/, 12000));
check("and says why it is asked this way", await sees(/direction that proves/));
await shot("32-practise-mistakes");

// ---- today's session ----------------------------------------------------
await page.goto(`${BASE}/session`, { waitUntil: "networkidle" });
check("session page builds a plan", await sees(/Today's session/));
check("the plan says how long it is", await sees(/in the order that teaches best/));
const blocks = await page.locator("ol > li .card").count();
check("the plan has blocks", blocks > 0, `${blocks} blocks`);
check("and leads with the specific thing that keeps failing",
  await sees(/pattern rather than bad luck/));
check("and says what it is aiming at",
  await sees(/What this session is aiming at/) || await sees(/Nothing to do right now/));
await shot("24-session");

// ---- pronunciation lab --------------------------------------------------
await page.goto(`${BASE}/pronunciation`, { waitUntil: "networkidle" });
await page.getByRole("tab", { name: /^Rules/ }).click();
check("korean rule index lists 받침 rules", await sees(/연음/));
await page.getByText(/연음/).first().click();
check("opening a rule explains it plainly, with the terminology behind a click",
  await sees(/The precise version/));
check("and shows a worked example the engine computed", await sees("한구거"));
await shot("25-rules");
await page.getByRole("tab", { name: /Say anything/ }).click();
await page.getByLabel("Text to analyse").fill("한국어");
await page.getByRole("button", { name: /^Explain$/ }).click();
check("the lab shows the actual pronunciation", await sees("한구거"));
await shot("26-explain");
check("korean has no pitch accent tab",
  (await page.getByRole("tab", { name: /Pitch accent/ }).count()) === 0);

// ---- japanese pitch accent ----------------------------------------------
await page.goto(`${BASE}/languages`, { waitUntil: "networkidle" });
await page.locator("article").filter({ hasText: "Japanese" })
  .getByRole("button", { name: /Switch to this/ }).click();
await page.waitForTimeout(900);
await page.goto(`${BASE}/pronunciation`, { waitUntil: "networkidle" });
check("japanese does have a pitch accent tab",
  (await page.getByRole("tab", { name: /Pitch accent/ }).count()) === 1);
await page.getByRole("tab", { name: /Pitch accent/ }).click();
check("the four shapes are shown", await sees(/heiban/));
check("the documented pairs are shown", await sees(/chopsticks/));
check("and the page says what is not shipped",
  await sees(/lexical and dialect-dependent/));
await shot("27-pitch-accent");
await page.goto(`${BASE}/languages`, { waitUntil: "networkidle" });
await page.locator("article").filter({ hasText: "Korean" })
  .getByRole("button", { name: /Switch to this/ }).click();
await page.waitForTimeout(900);

// ---- backups ------------------------------------------------------------
await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
check("data safety panel is present", await sees(/Backups and health/));
check("the integrity check reports a schema version", await sees(/schema v\d/));
check("and that the database is healthy", await sees(/^healthy$/));
await page.getByRole("button", { name: /Back up now/ }).click();
check("a backup appears in the list", await sees(/\.sqlite3/, 12000));
check("restoring explains that it is itself undoable",
  await sees(/can be undone the same way/));
await shot("28-backups");

await page.goto(`${BASE}/search`, { waitUntil: "networkidle" });
await page.getByLabel("Search").fill("먹");
await page.getByRole("button", { name: /^Search$/ }).click();
check("search finds 먹다", await sees("먹다"));
check("search also explains the pronunciation", await sees("How it sounds"));
await shot("21-search");

await page.goto(`${BASE}/conjugation`, { waitUntil: "networkidle" });
await page.getByLabel("Dictionary form").fill("춥다");
await page.getByRole("button", { name: /^Conjugate$/ }).click();
check("ㅂ irregular is explained, not just listed", await sees(/melts into a 우 sound/));
check("and the form is right", await sees("추워요"));
await shot("22-conjugation");

// ---- dark mode + phone --------------------------------------------------
await page.goto(`${BASE}/settings`, { waitUntil: "networkidle" });
const themeSelect = page.locator("select").filter({ hasText: "Match my system" }).first();
await themeSelect.selectOption("dark");
await page.waitForTimeout(900);   // the save is a round trip, even to localhost
await page.goto(`${BASE}/`, { waitUntil: "networkidle" });
check("dark theme applied", (await page.getAttribute("html", "data-theme")) === "dark");
await shot("18-dark");

const phone = await ctx.newPage();
await phone.setViewportSize({ width: 390, height: 844 });
await phone.goto(`${BASE}/`, { waitUntil: "networkidle" });
await phone.screenshot({ path: `${shots}/19-phone.png`, fullPage: true });
check("phone bottom bar present", (await phone.locator("nav[aria-label='Primary']").count()) === 1);

await browser.close();

let pass = 0;
for (const r of results) {
  console.log(`  ${r.cond ? "ok  " : "FAIL"} ${r.label}${r.cond ? "" : "  " + r.detail}`);
  if (r.cond) pass++;
}
console.log(`\n${pass}/${results.length} UI checks passed`);
if (errors.length) {
  console.log("\nBrowser errors:");
  for (const e of [...new Set(errors)].slice(0, 15)) console.log("  " + e);
}
process.exit(pass === results.length && errors.length === 0 ? 0 : 1);
