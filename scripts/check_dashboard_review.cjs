const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { chromium } = require('playwright');

async function verify() {
  const { url, email, password } = JSON.parse(readFileSync(process.argv[2], 'utf8').trim().split('\n')[0]);
  const browser = await chromium.launch({ executablePath: process.env.BH_CHROMIUM_EXECUTABLE });
  const outside = [];
  try {
    const context = await browser.newContext();
    await context.route('**/*', route => {
      if (new URL(route.request().url()).origin !== url) {
        outside.push(route.request().url());
        return route.abort();
      }
      return route.continue();
    });
    const page = await context.newPage();
    const unauthenticated = await page.request.get(`${url}/api/validation/pilot`);
    assert.equal(unauthenticated.status(), 401);
    await page.goto(url);
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Mot de passe').fill(password);
    await page.getByRole('button', { name: 'Se connecter' }).click();
    await page.waitForURL('**/validation');
    const identity = await page.evaluate(() => JSON.parse(localStorage.getItem('user')).id);
    for (const [label, button, status, opposite] of [
      ['A', 'Approuver', 'validated', 'rejected'],
      ['B', 'Rejeter', 'rejected', 'validated'],
    ]) {
      const subject = `Synthetic insurance recommendation ${label}`;
      await page.getByRole('button', { name: `${subject} · pending` }).click();
      assert.match(await page.locator('main').innerText(), /Synthetic Fleet Cover/);
      await page.getByRole('button', { name: button }).click();
      await page.getByRole('button', { name: `${subject} · ${status}` }).waitFor();
      const timestamp = await page.locator('time').getAttribute('datetime');
      assert.equal(new Date(timestamp).toISOString(), timestamp);
      await page.getByText(email, { exact: true }).waitFor();

      const retry = await page.evaluate(async ({ subject, opposite }) => {
        const headers = { Authorization: `Bearer ${localStorage.getItem('token')}`, 'Content-Type': 'application/json' };
        const path = '/api/validation/pilot';
        const rows = await (await fetch(path, { headers })).json();
        const { _id, reviewed_by } = rows.find(row => row.subject === subject);
        const response = await fetch(`${path}/${_id}`, {
          method: 'PATCH', headers,
          body: JSON.stringify({ decision: opposite, reviewed_by: 'forged', reviewed_at: '2000-01-01T00:00:00.000Z' }),
        });
        return { status: response.status, reviewed_by };
      }, { subject, opposite });
      assert.deepEqual(retry, { status: 409, reviewed_by: identity });

      await page.reload();
      await page.getByRole('button', { name: `${subject} · ${status}` }).click();
      assert.equal(await page.locator('time').getAttribute('datetime'), timestamp);
      await page.getByText(email, { exact: true }).waitFor();
      assert.equal(await page.getByRole('button', { name: 'Approuver' }).count(), 0);
      assert.equal(await page.getByRole('button', { name: 'Rejeter' }).count(), 0);
      console.log(`${status} stored and restored after reload; repeat request returned 409`);
    }
    const delivery = await page.request.post(`${url}/api/email`);
    assert.equal(delivery.status(), 404);
    assert.deepEqual(outside, []);
    console.log('Browser requests outside pilot: 0; delivery endpoint unavailable in pilot');
  } finally {
    await browser.close();
  }
}

verify().catch(error => { console.error(error); process.exitCode = 1; });
