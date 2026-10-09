import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';

// Keep the existing vector wordmark; email clients need a raster asset whose
// light backing survives dark-mode changes to the surrounding HTML background.
const source = await readFile(new URL('../public/brand/logo-wordmark.svg', import.meta.url), 'utf8');
const output = new URL('../public/brand/email-wordmark-v2.png', import.meta.url);
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 246, height: 64 }, deviceScaleFactor: 4 });
  await page.setContent(`<!doctype html><html><head><style>
    html,body{margin:0;width:246px;height:64px;background:#f6f4ed}
    body{display:flex;align-items:center;justify-content:center}
    svg{display:block;width:214px;height:40px}
  </style></head><body>${source}</body></html>`);
  await page.screenshot({ path: fileURLToPath(output), omitBackground: false });
  const png = await readFile(output);
  const details = await page.evaluate(async (dataUrl) => {
    const image = new Image();
    image.src = dataUrl;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext('2d');
    context.drawImage(image, 0, 0);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    for (let i = 3; i < pixels.length; i += 4) {
      if (pixels[i] !== 255) throw new Error('Email branding must be fully opaque');
    }
    if (pixels[0] !== 246 || pixels[1] !== 244 || pixels[2] !== 237) {
      throw new Error('Email branding must have the intended paper backing');
    }
    return { width: image.width, height: image.height, opaque: true };
  }, `data:image/png;base64,${png.toString('base64')}`);
  process.stdout.write(JSON.stringify({ bytes: png.length, ...details }) + '\n');
} finally {
  await browser.close();
}
