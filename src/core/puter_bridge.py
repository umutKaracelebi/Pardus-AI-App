"""
Puter Bridge - Python backend ile Puter.js frontend arasında köprü.
Ajan vision isteklerini frontend'e yönlendirir, frontend Puter.js ile yanıt alır.
"""
import os
import base64
import time
import threading


class PuterBridge:
    """Python'dan Puter.js'e vision isteği gönderir ve yanıt bekler."""

    def __init__(self):
        self._pending_request = None  # {prompt, image_b64, timestamp}
        self._response = None
        self._lock = threading.Lock()
        self._event = threading.Event()
        self.last_model_used = "Kimi K2.5 (Puter.js)"

    def generate_vision_response(self, prompt: str, image_path: str) -> str:
        """Vision API çağrısı - frontend Puter.js'e yönlendirir."""
        if not os.path.exists(image_path):
            raise Exception(f"Görsel bulunamadı: {image_path}")

        # Görseli base64'e çevir
        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()

        ext = os.path.splitext(image_path)[1].lower()
        mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}.get(ext, 'image/png')
        data_url = f"data:{mime};base64,{img_data}"

        # İsteği kuyruğa koy
        with self._lock:
            self._response = None
            self._event.clear()
            self._pending_request = {
                "prompt": prompt,
                "image_url": data_url,
                "timestamp": time.time()
            }

        print("☁️  Puter.js'e vision isteği gönderildi, yanıt bekleniyor...")

        # Yanıt bekle (max 60 saniye)
        got_response = self._event.wait(timeout=60)
        if not got_response or self._response is None:
            raise Exception("Puter.js yanıt vermedi (zaman aşımı 60s)")

        result = self._response
        with self._lock:
            self._pending_request = None
            self._response = None
        return result

    def get_pending_request(self):
        """Frontend bu endpoint'i poll eder - bekleyen istek var mı?"""
        with self._lock:
            if self._pending_request:
                return self._pending_request.copy()
        return None

    def submit_response(self, response_text: str):
        """Frontend Puter.js yanıtını buraya gönderir."""
        with self._lock:
            self._response = response_text
        self._event.set()
        print("   ✅ Puter.js'ten yanıt alındı.")
