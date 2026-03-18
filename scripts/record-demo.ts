import { chromium } from 'playwright';
import path from 'path';

const MR_URL = 'https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/41';
const OUTPUT_DIR = path.join(process.cwd(), '.playwright-mcp');

// GitLab uses a custom scroll container, not window
const SCROLL_CONTAINER = '.panel-content-inner.js-static-panel-inner';

async function smoothScroll(page: any, px: number) {
  await page.evaluate(
    ({ sel, px }: { sel: string; px: number }) => {
      const el = document.querySelector(sel);
      if (el) el.scrollBy({ top: px, behavior: 'smooth' });
    },
    { sel: SCROLL_CONTAINER, px }
  );
}

async function main() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    recordVideo: { dir: OUTPUT_DIR, size: { width: 1280, height: 720 } },
  });

  const page = await context.newPage();

  // Navigate to MR
  await page.goto(MR_URL, { waitUntil: 'domcontentloaded' });
  console.log('Page loaded, waiting for activity to render...');

  // Wait for the Kassandra Performance Report to appear (lazy-loaded)
  try {
    await page.waitForSelector('text=Kassandra Performance Report', { timeout: 30000 });
    console.log('Performance report found, waiting for Mermaid charts...');
  } catch {
    console.log('Report text not found after 30s, proceeding anyway...');
  }

  // Extra wait for Mermaid charts to render
  await page.waitForTimeout(5000);

  // Scroll to top of the container
  await page.evaluate((sel: string) => {
    const el = document.querySelector(sel);
    if (el) el.scrollTo({ top: 0 });
  }, SCROLL_CONTAINER);
  await page.waitForTimeout(1000);

  console.log('Starting smooth scroll demo...');

  // Pause at top — MR title and summary visible
  await page.waitForTimeout(3000);

  // Smooth scroll through the entire page
  const scrollSteps = [
    { px: 500, wait: 2500 },  // summary details + test plan
    { px: 500, wait: 2500 },  // merge status + activity start
    { px: 500, wait: 2500 },  // trigger comment
    { px: 500, wait: 2500 },  // kassandra reply + report header
    { px: 500, wait: 3000 },  // report summary table
    { px: 400, wait: 2500 },  // thresholds table
    { px: 400, wait: 2500 },  // latency distribution
    { px: 400, wait: 2500 },  // response time chart
    { px: 400, wait: 2500 },  // p95 latency chart
    { px: 400, wait: 2500 },  // timing breakdown table
    { px: 400, wait: 2500 },  // timing pie chart
    { px: 400, wait: 2500 },  // custom metrics
    { px: 400, wait: 2500 },  // validation checks pie
    { px: 400, wait: 2500 },  // kassandra's analysis header
    { px: 400, wait: 2500 },  // critical issue + highlights
    { px: 400, wait: 2500 },  // root cause
    { px: 400, wait: 3000 },  // recommendation + tagline
  ];

  for (const step of scrollSteps) {
    await smoothScroll(page, step.px);
    await page.waitForTimeout(step.wait);
  }

  console.log('Scroll complete, saving video...');

  // Close context to flush video
  const videoPath = await page.video()?.path();
  await context.close();
  await browser.close();

  console.log(`Video saved to: ${videoPath}`);
}

main().catch(console.error);
