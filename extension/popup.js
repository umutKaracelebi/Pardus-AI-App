// Kimi Token Auto-Capture — Popup Logic

document.addEventListener('DOMContentLoaded', init);

async function init() {
  await loadTokenStatus();
  setupEventListeners();
}

/**
 * Token durumunu yükle ve arayüzü güncelle
 */
async function loadTokenStatus() {
  try {
    const response = await chrome.runtime.sendMessage({ type: 'GET_TOKEN_STATUS' });
    updateUI(response);
  } catch (err) {
    console.error('Token status error:', err);
    updateUI({ status: 'none' });
  }
}

/**
 * Arayüzü güncelle
 */
function updateUI(data) {
  const statusDot = document.getElementById('statusDot');
  const statusText = document.getElementById('statusText');
  const tokenValue = document.getElementById('tokenValue');
  const tokenDisplay = document.getElementById('tokenDisplay');
  const tokenSource = document.getElementById('tokenSource');
  const tokenTime = document.getElementById('tokenTime');
  const apiUrlInput = document.getElementById('apiUrlInput');
  const copyBtn = document.getElementById('copyBtn');

  // Status indicator
  statusDot.className = 'status-dot ' + (data.status || 'none');

  const statusMessages = {
    active: '✅ Token Aktif',
    captured: '🟡 Token Yakalandı',
    expired: '❌ Token Süresi Dolmuş',
    none: '⏳ Token Bekleniyor'
  };
  statusText.textContent = statusMessages[data.status] || statusMessages.none;

  // Token display
  if (data.token) {
    // Token'ı kısalt — ilk 20 ve son 10 karakter göster
    const display = data.token.length > 40
      ? data.token.substring(0, 20) + '...' + data.token.slice(-10)
      : data.token;
    tokenValue.textContent = display;
    tokenDisplay.classList.remove('no-token');
    copyBtn.style.display = 'flex';
  } else {
    tokenValue.textContent = 'Token bulunamadı — kimi.com\'a giriş yapın';
    tokenDisplay.classList.add('no-token');
    copyBtn.style.display = 'none';
  }

  // Meta info
  if (data.source) {
    tokenSource.textContent = '📍 ' + data.source;
  }
  if (data.timestamp) {
    const time = new Date(data.timestamp);
    tokenTime.textContent = '🕐 ' + time.toLocaleTimeString('tr-TR');
  }

  // API URL
  apiUrlInput.value = data.apiUrl || 'http://localhost:8001';
}

/**
 * Event listener'ları kur
 */
function setupEventListeners() {
  // Token kopyala
  document.getElementById('copyBtn').addEventListener('click', async () => {
    try {
      const response = await chrome.runtime.sendMessage({ type: 'GET_TOKEN_STATUS' });
      if (response.token) {
        await navigator.clipboard.writeText(response.token);
        showToast('Token panoya kopyalandı! ✅', 'success');
      }
    } catch (err) {
      showToast('Kopyalama başarısız!', 'error');
    }
  });

  // Token yenile (aktif tab'dan content script'e mesaj gönder)
  document.getElementById('refreshBtn').addEventListener('click', async () => {
    try {
      // Aktif sekmeyi bul ve content script'e mesaj gönder
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      if (tab && (tab.url.includes('kimi.moonshot.cn') || tab.url.includes('kimi.com'))) {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => {
            const token = localStorage.getItem('refresh_token');
            if (token) {
              let processedToken = token;
              try {
                const parsed = JSON.parse(token);
                if (Array.isArray(parsed)) processedToken = parsed.join('.');
              } catch (e) {}
              processedToken = processedToken.replace(/^["']|["']$/g, '');

              chrome.runtime.sendMessage({
                type: 'KIMI_TOKEN_CAPTURED',
                token: processedToken,
                source: window.location.hostname,
                timestamp: Date.now()
              });
            }
          }
        });

        // Biraz bekle ve durumu yenile
        await new Promise(r => setTimeout(r, 500));
        await loadTokenStatus();
        showToast('Token yenilendi!', 'success');
      } else {
        showToast('Önce kimi.com açın!', 'info');
      }
    } catch (err) {
      showToast('Yenileme hatası: ' + err.message, 'error');
    }
  });

  // API Test
  document.getElementById('testApiBtn').addEventListener('click', async () => {
    const apiUrl = document.getElementById('apiUrlInput').value.trim();

    try {
      // Önce ping testi
      const pingResponse = await fetch(`${apiUrl}/ping`);
      const pingText = await pingResponse.text();

      if (pingText.trim() === 'pong') {
        // Token doğrulama
        const response = await chrome.runtime.sendMessage({ type: 'GET_TOKEN_STATUS' });

        if (response.token) {
          const checkResult = await chrome.runtime.sendMessage({
            type: 'CHECK_TOKEN_ALIVE',
            token: response.token,
            apiUrl: apiUrl
          });

          if (checkResult.live) {
            showToast('API ✅ Token Aktif!', 'success');
          } else {
            showToast(`API ✅ Token: ${checkResult.error || 'Doğrulanamadı'}`, 'info');
          }
        } else {
          showToast('API ✅ Sunucu çalışıyor', 'success');
        }

        await loadTokenStatus();
      }
    } catch (err) {
      showToast('API erişilemedi!', 'error');
    }
  });

  // API URL kaydet
  document.getElementById('saveUrlBtn').addEventListener('click', async () => {
    const apiUrl = document.getElementById('apiUrlInput').value.trim();
    if (!apiUrl) {
      showToast('URL boş olamaz!', 'error');
      return;
    }

    await chrome.runtime.sendMessage({
      type: 'UPDATE_API_URL',
      apiUrl: apiUrl
    });
    showToast('API URL kaydedildi!', 'success');
  });
}

/**
 * Toast bildirimi göster
 */
function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast ${type} show`;

  setTimeout(() => {
    toast.classList.remove('show');
  }, 2500);
}
