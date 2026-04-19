"""
Kimi Free API - Yerel kimi-free-api sunucusu üzerinden Kimi AI erişimi.
OpenAI-uyumlu endpoint (localhost:8002) kullanır.
refresh_token ile kimlik doğrulama yapar.
"""
import os
import json
import base64
import time
import re
import requests

# Token dosyası
_TOKEN_FILE = os.path.expanduser("~/.config/pardus_ai/kimi_refresh_token.txt")

# Kimi API proxy adresi (429 retry proxy)
KIMI_API_BASE = "http://localhost:8002"

# Kimlik temizleme
_IDENTITY_PATTERNS = [
    (r'(?i)ben\s+(ise\s+)?claude[^.]*\.?', ''),
    (r'(?i)claude\s+\d[\d.]*\s*(sonnet|opus|haiku)?', 'Kimi'),
    (r'(?i)anthropic[^.]*\.?', 'Moonshot AI'),
    (r'(?i)openai[^.]*gpt[^.]*\.?', 'Kimi'),
]


def _get_token():
    """Kaydedilmiş Kimi refresh_token'ını oku."""
    if os.path.exists(_TOKEN_FILE):
        with open(_TOKEN_FILE, 'r') as f:
            token = f.read().strip()
            if token:
                return token
    return None


def save_token(token: str):
    """Kimi refresh_token'ını kaydet."""
    os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)
    with open(_TOKEN_FILE, 'w') as f:
        f.write(token.strip())
    print(f"   ✅ Kimi refresh_token kaydedildi: {_TOKEN_FILE}")


def has_token() -> bool:
    """Token var mı kontrol et."""
    return _get_token() is not None


def delete_token():
    """Token'ı sil (yeniden kurulum için)."""
    if os.path.exists(_TOKEN_FILE):
        os.remove(_TOKEN_FILE)
        print("   🗑️ Kimi refresh_token silindi.")


def _clean_response(text: str) -> str:
    """AI yanıtından kimlik sızıntılarını temizle."""
    for pattern, replacement in _IDENTITY_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text.strip()


class KimiAPI:
    """Yerel kimi-free-api sunucusuna bağlanan OpenAI-uyumlu client."""

    MODEL = "moonshot-v1-vision"
    TEXT_MODEL = "moonshot-v1-128k"
    MAX_RETRIES = 3

    def __init__(self, token: str = None):
        self.token = token or _get_token()
        self.last_model_used = "Kimi (kimi-free-api)"
        if not self.token:
            raise Exception(
                "Kimi refresh_token bulunamadı! "
                "Lütfen kimi.com'a giriş yapın ve Chrome extension'dan token alın, "
                "veya Ayarlar > Token Ayarla kısmından manuel olarak girin."
            )
        self._session = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/json',
        })

    def _call_api(self, messages: list, model: str = None, stream: bool = False) -> str:
        """kimi-free-api OpenAI-uyumlu endpoint çağrısı."""
        payload = {
            'model': model or self.TEXT_MODEL,
            'messages': messages,
            'stream': stream,
            'use_search': False,
        }

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                if attempt > 0:
                    wait = 3 * attempt
                    print(f"   ⏳ Yeniden deniyor ({attempt + 1}/{self.MAX_RETRIES}), {wait}s bekleniyor...")
                    time.sleep(wait)

                r = self._session.post(
                    f"{KIMI_API_BASE}/v1/chat/completions",
                    json=payload,
                    headers={
                        'Authorization': f'Bearer {self.token}',
                    },
                    timeout=(10, 120),  # connect=10s, read=120s
                )

                if r.status_code == 401:
                    raise Exception(
                        "Kimi refresh_token süresi dolmuş. "
                        "Lütfen kimi.com'a tekrar giriş yapın ve token'ı yenileyin."
                    )
                if r.status_code == 429:
                    print("   ⚠️ Rate limit, bekleniyor...")
                    time.sleep(5)
                    continue
                if r.status_code != 200:
                    last_error = f"HTTP {r.status_code}: {r.text[:200]}"
                    continue

                data = r.json()

                # OpenAI-uyumlu yanıt formatı
                if 'choices' in data and len(data['choices']) > 0:
                    content = data['choices'][0].get('message', {}).get('content', '')
                    return _clean_response(content)

                last_error = f"Beklenmeyen yanıt formatı: {r.text[:200]}"

            except requests.exceptions.Timeout:
                last_error = f"Zaman aşımı (deneme {attempt + 1})"
                print(f"   ⚠️ {last_error}")
            except requests.exceptions.ConnectionError:
                last_error = f"Bağlantı hatası — kimi-free-api çalışıyor mu? (deneme {attempt + 1})"
                print(f"   ⚠️ {last_error}")
            except Exception as e:
                if "token" in str(e).lower():
                    raise
                last_error = str(e)
                print(f"   ⚠️ Hata: {last_error[:100]}")

        raise Exception(f"Kimi API yanıt veremedi: {last_error}")

    def generate_response(self, messages: list) -> str:
        """Sohbet yanıtı üret (G4FAPI/PuterAPI uyumlu)."""
        system_prompt = (
            "Sen 'Pardus AI Asistanı' adında bir yapay zeka asistanısın. "
            "Pardus Linux için geliştirildin. Kimi modelini kullanıyorsun. "
            "Biri sana hangi model olduğunu sorarsa 'Ben Pardus AI Asistanıyım, "
            "Kimi modeli üzerinde çalışıyorum' de. "
            "Kullanıcının yazdığı dilde yanıt ver. En iyi ve en detaylı yanıtı vermeye çalış."
        )

        formatted_messages = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, list):
                # PuterAPI/G4FAPI formatı — text parçalarını birleştir
                text_parts = [item["text"] for item in content if item.get("type", "") == "text"]
                formatted_content = " ".join(text_parts)
            else:
                formatted_content = content

            formatted_messages.append({
                "role": role,
                "content": formatted_content
            })

        return self._call_api(formatted_messages, model=self.TEXT_MODEL)

    def generate_vision_response(self, prompt: str, image_path: str) -> str:
        """Görsel analiz (vision) — base64 görsel + prompt.
        
        kimi-free-api Vision Guide formatına uygun:
        - image_url önce, text sonra
        - Tek user mesajı (system mesajı yok)
        - model: kimi
        """
        if not os.path.exists(image_path):
            raise Exception(f"Görsel bulunamadı: {image_path}")

        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()

        ext = os.path.splitext(image_path)[1].lower()
        mime = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp',
            '.gif': 'image/gif',
        }.get(ext, 'image/png')
        data_url = f"data:{mime};base64,{img_data}"

        # System prompt ZORUNLU — messages.length >= 2 olmalı ki
        # kimi-free-api dosya dikkat mekanizmasını (file attention injection) tetiklesin.
        # messages.length < 2 olursa passthrough moduna girer ve dosya referansı kaybolur.
        messages = [
            {"role": "system", "content": "Görseli analiz et ve Türkçe yanıt ver."},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt}
                ]
            }
        ]

        return self._call_api(messages, model="kimi")

    def generate_video_response(self, prompt: str, video_path: str) -> str:
        """Video analiz — frame'leri çıkarıp vision API ile analiz et."""
        if not os.path.exists(video_path):
            raise Exception(f"Video bulunamadı: {video_path}")

        try:
            import cv2
        except ImportError:
            raise Exception("Video analizi için opencv-python gerekli: pip install opencv-python")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("Video dosyası açılamadı.")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30

        # En fazla 4 frame çıkar (videodan eşit aralıkla)
        max_frames = 4
        frame_indices = []
        if total_frames <= max_frames:
            frame_indices = list(range(total_frames))
        else:
            step = total_frames / max_frames
            frame_indices = [int(step * i) for i in range(max_frames)]

        frames_b64 = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                b64 = base64.b64encode(buffer).decode()
                frames_b64.append(b64)
        cap.release()

        if not frames_b64:
            raise Exception("Videodan kare çıkarılamadı.")

        # Kılavuza göre: image_url ÖNCE, text SONRA, tek user mesajı
        content = []
        for b64 in frames_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })
        content.append({
            "type": "text",
            "text": (
                f"Türkçe yanıt ver. Bu bir videonun {len(frames_b64)} karesinden "
                f"oluşan analizidir. Videoyu bütünlüklü olarak değerlendir. "
                f"Kullanıcı sorusu: {prompt}"
            )
        })

        # System prompt ZORUNLU — messages.length >= 2 (dosya dikkat mekanizması)
        messages = [
            {"role": "system", "content": "Video karelerini analiz et ve Türkçe yanıt ver."},
            {"role": "user", "content": content}
        ]
        return self._call_api(messages, model="kimi")
