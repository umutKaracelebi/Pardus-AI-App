// Kimi Token Auto-Capture — Background Service Worker
// Content script'ten gelen token'ı yönetir ve badge durumunu günceller

const DEFAULT_API_URL = 'http://localhost:8001';
const PARDUS_BACKEND_URL = 'http://localhost:5789';

// Token mesajlarını dinle
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'KIMI_TOKEN_CAPTURED') {
    handleTokenCapture(message);
    sendResponse({ status: 'ok' });
  }
  if (message.type === 'GET_TOKEN_STATUS') {
    getTokenStatus().then(sendResponse);
    return true; // async response
  }
  if (message.type === 'CHECK_TOKEN_ALIVE') {
    checkTokenAlive(message.token, message.apiUrl).then(sendResponse);
    return true;
  }
  if (message.type === 'UPDATE_API_URL') {
    chrome.storage.local.set({ apiUrl: message.apiUrl });
    sendResponse({ status: 'ok' });
  }
});

/**
 * Yakalanan token'ı işle
 */
async function handleTokenCapture(message) {
  const { token, source, timestamp } = message;

  // Mevcut token ile karşılaştır
  const stored = await chrome.storage.local.get(['kimiToken', 'apiUrl']);
  const apiUrl = stored.apiUrl || DEFAULT_API_URL;

  // Token değişmişse güncelle
  if (stored.kimiToken !== token) {
    await chrome.storage.local.set({
      kimiToken: token,
      tokenSource: source,
      tokenTimestamp: timestamp,
      tokenStatus: 'captured'
    });

    console.log('[Kimi Token] New token captured from', source);

    // Pardus AI backend'ine otomatik gönder
    await sendTokenToPardus(token);

    // API'de doğrula
    await checkTokenAlive(token, apiUrl);
  }

  // Badge güncelle
  updateBadge('captured');
}

/**
 * Token'ın API'de geçerli olup olmadığını kontrol et
 */
async function checkTokenAlive(token, apiUrl) {
  if (!token) return { live: false, error: 'No token' };

  const url = apiUrl || DEFAULT_API_URL;

  try {
    const response = await fetch(`${url}/token/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token })
    });

    if (response.ok) {
      const data = await response.json();
      const status = data.live ? 'active' : 'expired';

      await chrome.storage.local.set({ tokenStatus: status });
      updateBadge(status);

      return { live: data.live, status };
    } else {
      await chrome.storage.local.set({ tokenStatus: 'captured' });
      updateBadge('captured');
      return { live: false, error: `HTTP ${response.status}` };
    }
  } catch (err) {
    // API erişilemezse token'ı "captured" olarak tut
    await chrome.storage.local.set({ tokenStatus: 'captured' });
    updateBadge('captured');
    return { live: false, error: err.message };
  }
}

/**
 * Token durumunu al
 */
async function getTokenStatus() {
  const data = await chrome.storage.local.get([
    'kimiToken',
    'tokenSource',
    'tokenTimestamp',
    'tokenStatus',
    'apiUrl'
  ]);
  return {
    token: data.kimiToken || null,
    source: data.tokenSource || null,
    timestamp: data.tokenTimestamp || null,
    status: data.tokenStatus || 'none',
    apiUrl: data.apiUrl || DEFAULT_API_URL
  };
}

/**
 * Badge rengini ve metnini güncelle
 */
function updateBadge(status) {
  const colors = {
    active: '#10B981',    // Yeşil
    captured: '#F59E0B',  // Turuncu
    expired: '#EF4444',   // Kırmızı
    none: '#6B7280'       // Gri
  };

  const texts = {
    active: '✓',
    captured: '●',
    expired: '✗',
    none: ''
  };

  chrome.action.setBadgeBackgroundColor({ color: colors[status] || colors.none });
  chrome.action.setBadgeText({ text: texts[status] || '' });
}

/**
 * Token'ı Pardus AI backend'ine otomatik gönder
 */
async function sendTokenToPardus(token) {
  if (!token) return;

  try {
    const response = await fetch(`${PARDUS_BACKEND_URL}/api/kimi/save-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token })
    });

    if (response.ok) {
      const data = await response.json();
      if (data.success) {
        console.log('[Kimi Token] ✅ Token Pardus AI backend\'ine gönderildi');
        return true;
      }
    }
    console.warn('[Kimi Token] Backend yanıt vermedi, token sadece eklentide saklandı');
  } catch (err) {
    // Backend çalışmıyorsa sessizce devam et
    console.warn('[Kimi Token] Pardus AI backend erişilemedi:', err.message);
  }
  return false;
}

// Başlangıçta badge'i ayarla ve mevcut token varsa backend'e gönder
chrome.runtime.onInstalled.addListener(async () => {
  updateBadge('none');
  console.log('[Kimi Token] Extension installed');

  // Mevcut token varsa backend'e gönder
  const data = await chrome.storage.local.get(['kimiToken']);
  if (data.kimiToken) {
    await sendTokenToPardus(data.kimiToken);
  }
});

// Periyodik token kontrolü ve backend'e gönderme (her 1 dakikada bir)
chrome.alarms.create('tokenCheck', { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === 'tokenCheck') {
    const data = await chrome.storage.local.get(['kimiToken', 'apiUrl']);
    if (data.kimiToken) {
      // Backend'e göndermeyi dene (yoksa zaten sessizce geçer)
      await sendTokenToPardus(data.kimiToken);
      // API'de doğrula
      await checkTokenAlive(data.kimiToken, data.apiUrl || DEFAULT_API_URL);
    }
  }
});

// Service worker başladığında da token'ı gönder
(async () => {
  const data = await chrome.storage.local.get(['kimiToken']);
  if (data.kimiToken) {
    await sendTokenToPardus(data.kimiToken);
  }
})();
