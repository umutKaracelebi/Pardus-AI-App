import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import fs from 'fs';

puppeteer.use(StealthPlugin());

(async () => {
    const browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,800']
    });
    const page = await browser.newPage();

    const token = fs.readFileSync('/home/umut/qwen_free/session/accounts/acc_1776549620459/token.txt', 'utf8');
    const cookiesStr = fs.readFileSync('/home/umut/qwen_free/session/accounts/acc_1776549616556/cookies.json', 'utf8');
    const cookies = JSON.parse(cookiesStr);
    await page.setCookie(...cookies);

    await page.setRequestInterception(true);
    page.on('request', request => {
        const url = request.url();
        if (url.includes('upload') || url.includes('sts') || url.includes('quark') || url.includes('file') || url.includes('chat')) {
            console.log(`[REQUEST] ${request.method()} ${url}`);
            const postData = request.postData();
            if (postData && postData.length < 5000) {
                console.log(`Payload: ${postData}`);
            }
        }
        request.continue();
    });

    page.on('response', async response => {
        const url = response.url();
        if (url.includes('upload') || url.includes('sts') || url.includes('quark') || url.includes('file') || url.includes('chat')) {
            console.log(`[RESPONSE] ${response.status()} ${url}`);
            try {
                const text = await response.text();
                if (text.length < 5000) {
                    console.log(`Body: ${text}`);
                }
            } catch (e) {}
        }
    });

    console.log('Navigating to chat.qwen.ai...');
    await page.goto('https://chat.qwen.ai', { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => localStorage.setItem('token', t), token);
    await page.goto('https://chat.qwen.ai', { waitUntil: 'domcontentloaded' });
    await new Promise(resolve => setTimeout(resolve, 5000));

    console.log('Finding file input...');
    const fileInput = await page.$('input[type="file"]');
    if (fileInput) {
        console.log('Uploading test.pdf...');
        await fileInput.uploadFile('/home/umut/qwen_free/test.pdf');
        console.log('File uploaded. Waiting 5 seconds...');
        await new Promise(resolve => setTimeout(resolve, 5000));
        
        console.log('Typing message...');
        // Instead of typing blindly, we can select the text area
        await page.type('textarea', 'What is this file?');
        await page.keyboard.press('Enter');
        console.log('Message sent. Waiting 10 seconds...');
        await new Promise(resolve => setTimeout(resolve, 10000));
    } else {
        console.log('No file input found!');
    }

    await browser.close();
})();
