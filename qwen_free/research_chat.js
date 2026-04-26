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

    const cookiesStr = fs.readFileSync('/home/umut/qwen_free/session/accounts/acc_1776549616556/cookies.json', 'utf8');
    const cookies = JSON.parse(cookiesStr);
    await page.setCookie(...cookies);

    await page.setRequestInterception(true);
    page.on('request', request => {
        const url = request.url();
        if (url.includes('chat/completions') || url.includes('/chats/') || url.includes('chat_completions') || url.includes('api/v2/files')) {
            if (request.method() === 'POST' || request.method() === 'PUT') {
                console.log(`[REQUEST] ${url}`);
                if (request.postData()) {
                    try { console.log(`Payload: ${JSON.stringify(JSON.parse(request.postData()), null, 2)}`); } 
                    catch(e) { console.log(`Payload: ${request.postData()}`); }
                }
            }
        }
        request.continue();
    });

    console.log('Navigating to chat.qwen.ai...');
    await page.goto('https://chat.qwen.ai', { waitUntil: 'domcontentloaded' });
    await new Promise(r => setTimeout(r, 5000));

    console.log('Simulating file drop...');
    
    // Read the file buffer
    const fileBuffer = fs.readFileSync('/home/umut/qwen_free/test.pdf');
    const fileBase64 = fileBuffer.toString('base64');
    
    // Create a DataTransfer object and dispatch drop event
    await page.evaluate(async (base64) => {
        const res = await fetch(`data:application/pdf;base64,${base64}`);
        const blob = await res.blob();
        const file = new File([blob], 'test.pdf', { type: 'application/pdf' });
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        
        const dropEvent = new DragEvent('drop', {
            dataTransfer: dataTransfer,
            bubbles: true,
            cancelable: true,
        });
        
        // Find the dropzone element (usually the whole page or chat area)
        document.querySelector('.chat-input-area, textarea, body').dispatchEvent(dropEvent);
    }, fileBase64);

    console.log('Drop event dispatched. Waiting 15 seconds for upload to process...');
    await new Promise(r => setTimeout(r, 15000));

    console.log('Sending message...');
    await page.keyboard.type('What is this file?');
    await page.keyboard.press('Enter');
    await new Promise(r => setTimeout(r, 15000));

    await browser.close();
})();
