"""
Puter API - Python'dan doğrudan Puter REST API çağrısı.
Token ile çalışır, tarayıcı/popup gerektirmez.
Ücretsiz, limitsiz, Kimi K2.5 destekli.
"""
import os
import json
import base64
import time
import requests
import re

# Token dosyası
_TOKEN_FILE = os.path.expanduser("~/.config/pardus_ai/puter_token.txt")

# Kimlik temizleme
_IDENTITY_PATTERNS = [
    (r'(?i)ben\s+(ise\s+)?claude[^.]*\.?', ''),
    (r'(?i)claude\s+\d[\d.]*\s*(sonnet|opus|haiku)?', 'Kimi K2.5'),
    (r'(?i)anthropic[^.]*\.?', 'Moonshot AI'),
    (r'(?i)openai[^.]*gpt[^.]*\.?', 'Kimi K2.5'),
]


def _get_token():
    """Kaydedilmiş Puter token'ını oku."""
    if os.path.exists(_TOKEN_FILE):
        with open(_TOKEN_FILE, 'r') as f:
            token = f.read().strip()
            if token:
                return token
    return None


def save_token(token: str):
    """Puter token'ını kaydet."""
    os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
    with open(_TOKEN_FILE, 'w') as f:
        f.write(token.strip())
    print(f"   ✅ Puter token kaydedildi: {_TOKEN_FILE}")


def has_token() -> bool:
    """Token var mı kontrol et."""
    return _get_token() is not None


def delete_token():
    """Token'ı sil (yeniden kurulum için)."""
    if os.path.exists(_TOKEN_FILE):
        os.remove(_TOKEN_FILE)
        print("   🗑️ Puter token silindi.")


def _clean_response(text: str) -> str:
    """AI yanıtından kimlik sızıntılarını temizle."""
    for pattern, replacement in _IDENTITY_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text.strip()


class PuterAPI:
    """Puter REST API - doğrudan Python'dan, popup yok, ücretsiz."""

    API_URL = "https://api.puter.com/drivers/call"
    MODEL = "kimi-k2.5"
    MAX_RETRIES = 3

    def __init__(self, token: str = None):
        self.token = token or _get_token()
        self.last_model_used = "Kimi K2.5 (Puter)"
        if not self.token:
            raise Exception(
                "Puter token bulunamadı! İlk kurulum gerekli."
            )
        # requests session for connection reuse
        self._session = requests.Session()
        self._session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Origin': 'https://puter.com'
        })

    def _call_ai(self, messages: list, model: str = None) -> str:
        """Puter AI API çağrısı — retry ve timeout korumalı."""
        payload = {
            'interface': 'puter-chat-completion',
            'driver': 'ai-chat',
            'method': 'complete',
            'args': {
                'messages': messages,
                'model': model or self.MODEL
            }
        }

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                if attempt > 0:
                    wait = 2 * attempt
                    print(f"   ⏳ Yeniden deniyor ({attempt + 1}/{self.MAX_RETRIES}), {wait}s bekleniyor...")
                    time.sleep(wait)

                r = self._session.post(
                    self.API_URL,
                    json=payload,
                    timeout=(10, 120)  # connect=10s, read=120s
                )

                if r.status_code == 401:
                    raise Exception("Puter token süresi dolmuş. Ayarlardan token'ı yenileyin.")
                if r.status_code == 429:
                    print("   ⚠️ Rate limit, bekleniyor...")
                    time.sleep(5)
                    continue
                if r.status_code != 200:
                    last_error = f"HTTP {r.status_code}: {r.text[:200]}"
                    continue

                data = r.json()
                if data.get('success'):
                    content = data['result']['message']['content']
                    return _clean_response(content)

                last_error = f"API yanıt hatası: {r.text[:200]}"

            except requests.exceptions.Timeout:
                last_error = f"Zaman aşımı (deneme {attempt + 1})"
                print(f"   ⚠️ {last_error}")
            except requests.exceptions.ConnectionError:
                last_error = f"Bağlantı hatası (deneme {attempt + 1})"
                print(f"   ⚠️ {last_error}")
            except Exception as e:
                if "token" in str(e).lower():
                    raise  # Token hatası direkt fırlat
                last_error = str(e)
                print(f"   ⚠️ Hata: {last_error[:100]}")

        raise Exception(f"Puter API yanıt veremedi: {last_error}")

    def generate_response(self, messages: list) -> str:
        """Sohbet yanıtı üret (pollinations_api uyumlu)."""
        system_prompt = (
            "Sen 'Pardus AI Asistanı' adında bir yapay zeka asistanısın. "
            "Pardus Linux için geliştirildin. Kimi K2.5 açık kaynak modelini kullanıyorsun. "
            "Biri sana hangi model olduğunu sorarsa 'Ben Pardus AI Asistanıyım, "
            "Kimi K2.5 açık kaynak modeli üzerinde çalışıyorum' de. "
            "Kullanıcının yazdığı dilde yanıt ver. En iyi ve en detaylı yanıtı vermeye çalış."
        )

        simple_messages = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            role = msg["role"]
            content_list = msg["content"]
            text_parts = []
            for item in content_list:
                if item["type"] == "text":
                    text_parts.append(item["text"])
            if text_parts:
                simple_messages.append({
                    "role": role,
                    "content": " ".join(text_parts)
                })

        return self._call_ai(simple_messages)

    def generate_vision_response(self, prompt: str, image_path: str) -> str:
        """Görsel analiz (vision) — base64 görsel + prompt."""
        if not os.path.exists(image_path):
            raise Exception(f"Görsel bulunamadı: {image_path}")

        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()

        ext = os.path.splitext(image_path)[1].lower()
        mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}.get(ext, 'image/png')
        data_url = f"data:{mime};base64,{img_data}"

        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}}
            ]
        }]

        return self._call_ai(messages)
