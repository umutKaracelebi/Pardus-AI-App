// Kimi Token Auto-Capture — Bridge Script
// localhost (Pardus AI) sayfalarında çalışır
// Extension background'dan token'ı alıp backend'e otomatik gönderir

(function () {
  'use strict';

  // Sadece setup sayfasında veya ana sayfada çalış
  if (!window.location.href.includes('localhost') && !window.location.href.includes('127.0.0.1')) return;

  async function forwardTokenToBackend() {
    try {
      // Extension background'dan token durumunu al
      const response = await chrome.runtime.sendMessage({ type: 'GET_TOKEN_STATUS' });

      if (response && response.token && response.token.length > 10) {
        console.log('[Kimi Bridge] Token eklentide bulundu, backend\'e gönderiliyor...');

        // Backend'e POST et
        const result = await fetch('/api/kimi/save-token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: response.token })
        });

        const data = await result.json();
        if (data.success) {
          console.log('[Kimi Bridge] ✅ Token backend\'e kaydedildi!');

          // Sayfada bildirim göster (varsa)
          const statusEl = document.getElementById('bridge-status');
          if (statusEl) {
            statusEl.innerHTML = '<span style="color:#3fb950">✅ Token eklentiden otomatik alındı!</span>';
          }
          const resultEl = document.getElementById('result');
          if (resultEl) {
            resultEl.innerHTML = '<span style="color:#3fb950">✅ Token otomatik kaydedildi! Bu pencereyi kapatabilirsiniz.</span>';
          }

          // Custom event fırlat — JavaScript tarafından dinlenebilir
          window.dispatchEvent(new CustomEvent('kimi-token-saved', { detail: { token: response.token } }));
        }
      } else {
        console.log('[Kimi Bridge] Eklentide token yok henüz.');
      }
    } catch (err) {
      console.warn('[Kimi Bridge] Hata:', err.message);
    }
  }

  // Hemen çalıştır
  forwardTokenToBackend();

  // 5 saniyede bir tekrar dene (token henüz gelmemiş olabilir)
  const interval = setInterval(async () => {
    try {
      // Token zaten kaydedildi mi kontrol et
      const status = await fetch('/api/kimi/status');
      const data = await status.json();
      if (data.has_token) {
        console.log('[Kimi Bridge] Token zaten mevcut, durduruluyor.');
        clearInterval(interval);
        return;
      }
    } catch (e) {}

    forwardTokenToBackend();
  }, 5000);

  // 3 dakika sonra durdur
  setTimeout(() => clearInterval(interval), 180000);

  console.log('[Kimi Bridge] Bridge script loaded on', window.location.hostname);
})();
