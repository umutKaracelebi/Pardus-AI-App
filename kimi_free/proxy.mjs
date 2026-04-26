/**
 * Kimi Free API — 429 Retry Proxy
 * 
 * Sadece 429 hatası geldiğinde exponential backoff ile yeniden dener.
 * Hiçbir rate limit uygulamaz — istekleri olduğu gibi geçirir.
 * 
 * Proxy port: 8002 → Hedef: localhost:8001
 */

import http from 'http';

const CONFIG = {
  PROXY_PORT: 8002,
  TARGET_HOST: 'localhost',
  TARGET_PORT: 8001,
  MAX_RETRIES: 3,
  INITIAL_BACKOFF_MS: 5000,
  MAX_BACKOFF_MS: 60000,
};

const stats = {
  total: 0,
  success: 0,
  retried: 0,
  failed: 0,
  rateLimited: 0,
  start: Date.now(),
};

function proxyRequest(req, body) {
  return new Promise((resolve, reject) => {
    const opts = {
      hostname: CONFIG.TARGET_HOST,
      port: CONFIG.TARGET_PORT,
      path: req.url,
      method: req.method,
      headers: { ...req.headers, host: `${CONFIG.TARGET_HOST}:${CONFIG.TARGET_PORT}` },
    };
    const p = http.request(opts, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => resolve({ statusCode: res.statusCode, headers: res.headers, body: data }));
    });
    p.on('error', reject);
    if (body) p.write(body);
    p.end();
  });
}

async function handleWithRetry(req, body) {
  for (let attempt = 0; attempt <= CONFIG.MAX_RETRIES; attempt++) {
    if (attempt > 0) {
      stats.retried++;
      const backoff = Math.min(CONFIG.INITIAL_BACKOFF_MS * Math.pow(2, attempt - 1), CONFIG.MAX_BACKOFF_MS);
      const wait = backoff + Math.random() * 1000;
      log(`⏳ 429 retry ${attempt}/${CONFIG.MAX_RETRIES} — ${(wait/1000).toFixed(1)}s bekleniyor...`);
      await new Promise(r => setTimeout(r, wait));
    }
    try {
      const result = await proxyRequest(req, body);
      if (result.statusCode === 429) {
        stats.rateLimited++;
        log(`🚫 429 geldi (deneme ${attempt + 1})`);
        continue;
      }
      // Kimi rate limit mesajı kontrolü
      try {
        const p = JSON.parse(result.body);
        if (p.code < 0 && p.message && (p.message.includes('限') || p.message.includes('频'))) {
          stats.rateLimited++;
          log(`🚫 Kimi limit: ${p.message} (deneme ${attempt + 1})`);
          continue;
        }
      } catch {}
      return result;
    } catch (err) {
      log(`❌ Bağlantı hatası: ${err.message}`);
      if (attempt === CONFIG.MAX_RETRIES) return { statusCode: 502, headers: {}, body: `{"error":"${err.message}"}` };
    }
  }
  stats.failed++;
  return { statusCode: 429, headers: {}, body: '{"error":"Rate limited, retries exhausted"}' };
}

const server = http.createServer((req, res) => {
  stats.total++;

  if (req.url === '/proxy/stats') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ...stats, uptime: Math.floor((Date.now() - stats.start) / 1000) }, null, 2));
    return;
  }

  let body = '';
  req.on('data', c => body += c);
  req.on('end', async () => {
    try {
      const result = await handleWithRetry(req, body || null);
      const h = { ...result.headers };
      delete h['transfer-encoding'];
      res.writeHead(result.statusCode, h);
      res.end(result.body);
      stats.success++;
    } catch (err) {
      stats.failed++;
      res.writeHead(502);
      res.end(`{"error":"${err.message}"}`);
    }
  });
});

function log(msg) {
  console.log(`[${new Date().toLocaleTimeString('tr-TR')}] ${msg}`);
}

server.listen(CONFIG.PROXY_PORT, () => {
  console.log(`\n🛡️  Kimi 429 Retry Proxy — :${CONFIG.PROXY_PORT} → :${CONFIG.TARGET_PORT}`);
  console.log(`   Retry: ${CONFIG.MAX_RETRIES}x | Backoff: ${CONFIG.INITIAL_BACKOFF_MS/1000}s-${CONFIG.MAX_BACKOFF_MS/1000}s`);
  console.log(`   Stats: http://localhost:${CONFIG.PROXY_PORT}/proxy/stats\n`);
});
