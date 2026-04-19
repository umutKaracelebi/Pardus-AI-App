// Kimi Token Auto-Capture — Content Script
// kimi.moonshot.cn ve kimi.com sayfalarında LocalStorage'dan refresh_token okur

(function () {
  'use strict';

  const TOKEN_KEY = 'refresh_token';
  const CHECK_INTERVAL = 15000; // 15 saniye

  /**
   * LocalStorage'dan refresh_token'ı oku ve background'a gönder
   */
  function captureToken() {
    try {
      let rawToken = localStorage.getItem(TOKEN_KEY);

      if (!rawToken) {
        // Bazı versiyonlarda farklı key isimleri olabilir
        const alternativeKeys = ['refresh_token', 'token', 'access_token'];
        for (const key of alternativeKeys) {
          rawToken = localStorage.getItem(key);
          if (rawToken) break;
        }
      }

      if (!rawToken) return;

      // Token bir JSON dizisi olabilir — "." ile birleştir (README'ye göre)
      let token = rawToken;
      try {
        const parsed = JSON.parse(rawToken);
        if (Array.isArray(parsed)) {
          token = parsed.join('.');
        }
      } catch (e) {
        // JSON değilse düz string olarak kullan
      }

      // Temizle - tırnak işaretlerini kaldır
      token = token.replace(/^["']|["']$/g, '');

      if (token && token.length > 10) {
        chrome.runtime.sendMessage({
          type: 'KIMI_TOKEN_CAPTURED',
          token: token,
          source: window.location.hostname,
          timestamp: Date.now()
        });
      }
    } catch (err) {
      console.warn('[Kimi Token Capture] Error:', err.message);
    }
  }

  // İlk yüklemede token'ı yakala
  captureToken();

  // Periyodik olarak kontrol et
  setInterval(captureToken, CHECK_INTERVAL);

  // Sayfa görünürlüğü değiştiğinde de kontrol et
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      captureToken();
    }
  });

  // Storage değişikliklerini dinle
  window.addEventListener('storage', (event) => {
    if (event.key === TOKEN_KEY) {
      captureToken();
    }
  });

  console.log('[Kimi Token Capture] Content script loaded on', window.location.hostname);
})();
