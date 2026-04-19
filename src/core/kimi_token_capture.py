"""
Kimi Token Capture — Chrome CDP ile otomatik refresh_token yakalama.
Kullanıcı kimi.com'a giriş yaptığında token otomatik olarak çekilir ve kaydedilir.
"""
import json
import time
import subprocess
import os
import signal
import requests

TOKEN_FILE = os.path.expanduser("~/.config/pardus_ai/kimi_refresh_token.txt")
CDP_PORT = 9223  # Ayrı port, mevcut Chrome'la çakışmasın


def _find_chrome():
    """Sistemdeki Chrome binary'sini bul."""
    for path in [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/snap/bin/chromium",
    ]:
        if os.path.exists(path):
            return path
    return None


def _get_ws_url(tab_filter="kimi"):
    """CDP üzerinden kimi tab'ının WebSocket URL'ini al."""
    try:
        r = requests.get(f"http://localhost:{CDP_PORT}/json", timeout=3)
        tabs = r.json()
        for t in tabs:
            if tab_filter in t.get("url", "").lower():
                return t.get("webSocketDebuggerUrl")
        # Kimi tab yoksa herhangi bir tab
        if tabs:
            return tabs[0].get("webSocketDebuggerUrl")
    except Exception:
        pass
    return None


def _eval_js(ws_url, expression):
    """CDP WebSocket ile JavaScript çalıştır."""
    try:
        import websocket
        ws = websocket.create_connection(
            ws_url, timeout=5,
            suppress_origin=True,
            header=["Origin: http://localhost"]
        )
        cmd = {
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True
            }
        }
        ws.send(json.dumps(cmd))
        result = json.loads(ws.recv())
        ws.close()
        return result.get("result", {}).get("result", {}).get("value")
    except Exception as e:
        return None


def capture_token_interactive():
    """
    Chrome'u kimi.com ile açıp, giriş yapıldıktan sonra
    refresh_token'ı otomatik yakalayıp kaydet.
    
    Returns: str | None — yakalanan token veya None
    """
    chrome = _find_chrome()
    if not chrome:
        print("   ❌ Chrome bulunamadı!")
        return None

    print("   🌐 Kimi.com açılıyor... Lütfen giriş yapın.")
    print("      Giriş yapıldığında token otomatik yakalanacak.\n")

    # Chrome'u remote debugging ile başlat
    chrome_proc = subprocess.Popen(
        [
            chrome,
            f"--remote-debugging-port={CDP_PORT}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            "https://kimi.moonshot.cn",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Chrome'un açılmasını bekle
    time.sleep(3)

    # Token yakalanana kadar bekle (max 180 saniye = 3 dakika)
    token = None
    for i in range(180):
        ws_url = _get_ws_url("kimi")
        if ws_url:
            # refresh_token kontrol et
            val = _eval_js(ws_url, 'localStorage.getItem("refresh_token")')
            if val and len(str(val)) > 10:
                token = str(val).strip().strip('"').strip("'")
                break

        if i > 0 and i % 10 == 0:
            print(f"      ⏳ Token bekleniyor... ({i}s)")

        time.sleep(1)

    if token:
        # Token'ı kaydet
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        print(f"   ✅ Token yakalandı ve kaydedildi!")
    else:
        print("   ⚠️ Token yakalanamadı. Süre doldu veya giriş yapılmadı.")

    # Chrome debug penceresi hala açık kalabilir, kapatmıyoruz
    # kullanıcı isterse kapatır
    return token


def has_saved_token():
    """Token dosyası var mı kontrol et."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return len(f.read().strip()) > 10
    return False
