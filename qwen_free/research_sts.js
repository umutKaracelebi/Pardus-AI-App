import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import fs from 'fs';

puppeteer.use(StealthPlugin());

(async () => {
    const browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();

    const cookiesStr = fs.readFileSync('/home/umut/qwen_free/session/accounts/acc_1776549616556/cookies.json', 'utf8');
    const cookies = JSON.parse(cookiesStr);
    await page.setCookie(...cookies);

    console.log('Navigating to chat.qwen.ai...');
    await page.goto('https://chat.qwen.ai', { waitUntil: 'domcontentloaded' });
    await new Promise(r => setTimeout(r, 3000));

    console.log('Fetching STS token...');
    const result = await page.evaluate(async () => {
        const token = localStorage.getItem('token');
        const res = await fetch('/api/v2/files/getstsToken', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                filename: 'test.pdf',
                filesize: 13264,
                filetype: 'document'
            })
        });
        return {
            status: res.status,
            body: await res.text()
        };
    });

    console.log('Result:', result);
    await browser.close();
})();
