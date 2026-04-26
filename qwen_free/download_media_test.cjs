const fs = require('fs');
const path = require('path');
const https = require('https');

const API_URL = 'http://127.0.0.1:3264/api/chat';
const TOKEN = '$oy*7REkTge5lnL*JpG9D40a3Md4_LZIdmI8sXK8F3CX5fbazzp_8Gn1gsBy1ogROHqapzX0Ccdj0';

async function downloadFile(url, filepath) {
    return new Promise((resolve, reject) => {
        const file = fs.createWriteStream(filepath);
        https.get(url, (response) => {
            response.pipe(file);
            file.on('finish', () => {
                file.close();
                resolve(filepath);
            });
        }).on('error', (err) => {
            fs.unlink(filepath, () => {});
            reject(err);
        });
    });
}

async function generateAndDownload() {
    console.log('--- Generating Image (A futuristic city) ---');
    let res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${TOKEN}` },
        body: JSON.stringify({
            model: 'qwen-max-latest',
            messages: [{ role: 'user', content: 'A futuristic city at night with flying cars and neon lights, high quality, cyberpunk style' }],
            chatType: 't2i',
            stream: false
        })
    });
    let data = await res.json();
    let imgUrl = data.video_url || (data.choices && data.choices[0] && data.choices[0].message.content);
    if (imgUrl && imgUrl.startsWith('http')) {
        console.log('Image generated! URL:', imgUrl);
        console.log('Downloading image...');
        await downloadFile(imgUrl, path.join(__dirname, 'test_output_image.jpg'));
        console.log('Image downloaded as test_output_image.jpg');
    } else {
        console.log('Failed to generate image:', JSON.stringify(data));
    }

    console.log('\n--- Generating Video (A cat playing with yarn) ---');
    res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${TOKEN}` },
        body: JSON.stringify({
            model: 'qwen-max-latest',
            messages: [{ role: 'user', content: 'A cute orange cat playing with a red ball of yarn on a wooden floor' }],
            chatType: 't2v',
            stream: false
        })
    });
    data = await res.json();
    let vidUrl = data.video_url || (data.choices && data.choices[0] && data.choices[0].message.content);
    if (vidUrl && vidUrl.startsWith('http')) {
        console.log('Video generated! URL:', vidUrl);
        console.log('Downloading video...');
        await downloadFile(vidUrl, path.join(__dirname, 'test_output_video.mp4'));
        console.log('Video downloaded as test_output_video.mp4');
    } else {
        console.log('Failed to generate video:', JSON.stringify(data));
    }
}

generateAndDownload().catch(console.error);
