import { chromium } from 'playwright';
import { spawn } from 'child_process';
import dns from 'dns';

// Force ipv4 resolution first
dns.setDefaultResultOrder('ipv4first');

async function main() {
  console.log('Starting Vite preview server...');
  const viteProcess = spawn('npx', ['vite', 'preview', '--port', '3000'], {
    cwd: process.cwd(),
    shell: true,
  });

  // Wait 5 seconds for preview server to spin up
  await new Promise((resolve) => setTimeout(resolve, 5000));

  let browser;
  let exitCode = 0;

  try {
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    await page.goto('http://localhost:3000/render-box?theme=dark', { waitUntil: 'networkidle' });
    await page.waitForFunction(() => typeof window.__CLOCK_CONTROLLER__ !== 'undefined', { timeout: 15000 });

    // 1. Freeze
    await page.evaluate(() => {
      window.__CLOCK_CONTROLLER__.freeze();
    });

    const getFirstCircleOffset = async () => {
      return await page.evaluate(() => {
        const circle = document.querySelector('circle');
        if (!circle) return null;
        const val = getComputedStyle(circle).offsetDistance;
        if (!val) return 0;
        if (val.endsWith('%')) return parseFloat(val);
        return parseFloat(val);
      });
    };

    const initialOffset = await getFirstCircleOffset();
    console.log('Initial offset (after freeze):', initialOffset);

    // Advance 1000ms
    await page.evaluate(() => window.__CLOCK_CONTROLLER__.advance(1000));
    const offset1 = await getFirstCircleOffset();
    console.log('Offset 1 (after 1000ms):', offset1);

    // Advance 1000ms
    await page.evaluate(() => window.__CLOCK_CONTROLLER__.advance(1000));
    const offset2 = await getFirstCircleOffset();
    console.log('Offset 2 (after 2000ms):', offset2);

    // Advance 1000ms
    await page.evaluate(() => window.__CLOCK_CONTROLLER__.advance(1000));
    const offset3 = await getFirstCircleOffset();
    console.log('Offset 3 (after 3000ms):', offset3);

    // Advance 1000ms
    await page.evaluate(() => window.__CLOCK_CONTROLLER__.advance(1000));
    const offset4 = await getFirstCircleOffset();
    console.log('Offset 4 (after 4000ms):', offset4);

    const diff1 = offset1 - initialOffset;
    const diff2 = offset2 - offset1;
    const diff3 = offset3 - offset2;
    const diff4 = offset4 - offset3;

    console.log(`Deltas: diff1=${diff1}%, diff2=${diff2}%, diff3=${diff3}%, diff4=${diff4}%`);

  } catch (err) {
    console.error('Error:', err);
    exitCode = 1;
  } finally {
    if (browser) await browser.close();
    viteProcess.kill('SIGINT');
  }
  process.exit(exitCode);
}

main();
