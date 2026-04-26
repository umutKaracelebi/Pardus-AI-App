"""
Qwen Free API - Yerel qwen-free-api sunucusu üzerinden Qwen AI erişimi.
OpenAI-uyumlu endpoint (localhost:3264) kullanır.
Puppeteer tabanlı Qwen proxy ile çalışır.
"""
import os
import json
import base64
import time
import re
import requests


# Qwen API proxy adresi
QWEN_API_BASE = "http://localhost:3264/api"

# Kimlik temizleme
_IDENTITY_PATTERNS = [
    (r'(?i)ben\s+(ise\s+)?(?:claude|gpt|gemini|chatgpt|copilot|deepseek|llama|mistral)[^\.\n]*\.?', ''),
    (r'(?i)claude\s+\d[\d.]*\s*(sonnet|opus|haiku)?', 'Qwen'),
    (r'(?i)gpt-?[\d.]+\s*\w*', 'Qwen'),
    (r'(?i)gemini\s+[\d.]+\s*\w*', 'Qwen'),
    (r'(?i)anthropic[^\.\n]*\.?', 'Alibaba Cloud'),
    (r'(?i)openai[^\.\n]*gpt[^\.\n]*\.?', 'Qwen'),
    (r"(?i)I(?:'m|\s+am)\s+(?:a\s+)?(?:Claude|GPT|Gemini|ChatGPT|Copilot|DeepSeek)\S*",
     "I am Pardus AI Assistant (powered by Qwen model)"),
    (r'(?:made|created|developed|built)\s+by\s+(?:Anthropic|OpenAI|Moonshot|Google|Meta)',
     'developed for Pardus Linux'),
]


def _clean_response(text: str) -> str:
    """AI yanıtından kimlik sızıntılarını temizle."""
    for pattern, replacement in _IDENTITY_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text.strip()


class QwenAPI:
    """Yerel qwen-free-api sunucusuna bağlanan OpenAI-uyumlu client."""

    DEFAULT_MODEL = "qwen-max-latest"
    VISION_MODEL = "qwen3-vl-max"
    MAX_RETRIES = 3

    def __init__(self):
        self.last_model_used = "Qwen (qwen-free-api)"
        self._session = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/json',
        })

    def _call_api(self, messages: list, model: str = None, stream: bool = False) -> str:
        """qwen-free-api OpenAI-uyumlu endpoint çağrısı."""
        payload = {
            'model': model or self.DEFAULT_MODEL,
            'messages': messages,
            'stream': stream,
        }

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                if attempt > 0:
                    wait = 3 * attempt
                    print(f"   ⏳ Yeniden deniyor ({attempt + 1}/{self.MAX_RETRIES}), {wait}s bekleniyor...")
                    time.sleep(wait)

                r = self._session.post(
                    f"{QWEN_API_BASE}/chat/completions",
                    json=payload,
                    timeout=(10, 180),  # connect=10s, read=180s
                )

                if r.status_code == 401:
                    raise Exception(
                        "Qwen hesap token'ı geçersiz. "
                        "Lütfen qwen_free sunucusunu yeniden başlatıp hesap ekleyin."
                    )
                if r.status_code == 429:
                    print("   ⚠️ Rate limit, bekleniyor...")
                    time.sleep(5)
                    continue
                if r.status_code != 200:
                    last_error = f"HTTP {r.status_code}: {r.text[:200]}"
                    continue

                # Streaming yanıt (SSE) parse et
                if stream:
                    return self._parse_sse_response(r)

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
                last_error = f"Bağlantı hatası — qwen-free-api çalışıyor mu? (deneme {attempt + 1})"
                print(f"   ⚠️ {last_error}")
            except Exception as e:
                if "token" in str(e).lower() or "hesap" in str(e).lower():
                    raise
                last_error = str(e)
                print(f"   ⚠️ Hata: {last_error[:100]}")

        raise Exception(f"Qwen API yanıt veremedi: {last_error}")

    def _parse_sse_response(self, response) -> str:
        """SSE (Server-Sent Events) yanıtını parse et."""
        full_content = ""
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            json_str = line[5:].strip()
            if json_str == "[DONE]":
                break
            try:
                chunk = json.loads(json_str)
                if chunk.get('choices') and chunk['choices'][0].get('delta', {}).get('content'):
                    full_content += chunk['choices'][0]['delta']['content']
            except (json.JSONDecodeError, KeyError, IndexError):
                pass
        return _clean_response(full_content)

    def generate_response(self, messages: list) -> str:
        """Sohbet yanıtı üret (PollinationsAPI/KimiAPI uyumlu arayüz).

        messages formatı:
        [{"role": "user", "content": [{"type": "text", "text": "..."}]}]
        """
        system_prompt = (
            "Sen 'Pardus AI Asistanı' adında bir yapay zeka asistanısın. "
            "Pardus Linux için geliştirildin. Qwen modelini kullanıyorsun. "
            "Biri sana hangi model olduğunu sorarsa 'Ben Pardus AI Asistanıyım, "
            "Qwen modeli üzerinde çalışıyorum' de. "
            "Kullanıcının yazdığı dilde yanıt ver. En iyi ve en detaylı yanıtı vermeye çalış."
        )

        formatted_messages = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, list):
                # Pardus içi format — text parçalarını birleştir
                text_parts = [item["text"] for item in content if item.get("type", "") == "text"]
                formatted_content = " ".join(text_parts)
            else:
                formatted_content = content

            formatted_messages.append({
                "role": role,
                "content": formatted_content
            })

        return self._call_api(formatted_messages, model=self.DEFAULT_MODEL)

    def generate_vision_response(self, prompt: str, image_path: str) -> str:
        """Görsel analiz (vision) — base64 görsel + prompt.

        Qwen VL modelleri kullanılarak görsel analiz yapılır.
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
            '.bmp': 'image/bmp',
        }.get(ext, 'image/png')
        data_url = f"data:{mime};base64,{img_data}"

        messages = [
            {"role": "system", "content": "Görseli analiz et ve kullanıcının dilinde yanıt ver."},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt}
                ]
            }
        ]

        self.last_model_used = f"Qwen ({self.VISION_MODEL})"
        return self._call_api(messages, model=self.VISION_MODEL)

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
        duration = total_frames / fps if fps > 0 else 0

        # En fazla 4 frame çıkar (videodan eşit aralıkla)
        max_frames = 4
        if total_frames <= max_frames:
            frame_indices = list(range(total_frames))
        else:
            step = total_frames / max_frames
            frame_indices = [int(step * i) for i in range(max_frames)]

        frames_b64 = []
        frame_times = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                b64 = base64.b64encode(buffer).decode()
                frames_b64.append(b64)
                frame_times.append(idx / fps if fps > 0 else 0)
        cap.release()

        if not frames_b64:
            raise Exception("Videodan kare çıkarılamadı.")

        print(f"   → {len(frames_b64)} kare çıkarıldı (süre: {duration:.1f}s)")

        # Ses transkripsiyonu (opsiyonel)
        audio_transcript = ""
        try:
            audio_transcript = self._transcribe_audio(video_path)
            if audio_transcript:
                print(f"   → Ses transkripsiyonu alındı ({len(audio_transcript)} karakter)")
        except Exception as e:
            print(f"   → Ses transkripsiyon hatası: {str(e)[:60]}")

        # Ses analizi (opsiyonel)
        audio_description = ""
        try:
            from src.core.audio_analyzer import analyze_audio
            audio_result = analyze_audio(video_path)
            if audio_result['has_audio'] and audio_result['description']:
                audio_description = audio_result['description']
                print(f"   → Ses sınıflandırması: {audio_description[:80]}...")
        except Exception as e:
            print(f"   → Ses sınıflandırma hatası: {str(e)[:80]}")

        # Multi-image mesaj oluştur
        time_info = ', '.join([f"Kare {i+1}: {t:.1f}s" for i, t in enumerate(frame_times)])

        prompt_parts = [
            f"Bu bir videonun {len(frames_b64)} karesinden oluşan analizidir.",
            f"Video süresi: {duration:.1f} saniye.",
            f"Karelerin zamanları: {time_info}."
        ]

        if audio_transcript:
            prompt_parts.append(f"\nVideodaki konuşma transkripsiyonu:\n\"{audio_transcript}\"")
        if audio_description:
            prompt_parts.append(f"\nSes analizi:\n{audio_description}")
        if not audio_transcript and not audio_description:
            prompt_parts.append("\nVideoda ses tespit edilemedi.")

        prompt_parts.append(f"\nKullanıcı sorusu: {prompt}")

        content = [{"type": "text", "text": " ".join(prompt_parts)}]
        for b64 in frames_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })

        messages = [
            {"role": "system", "content": "Video karelerini analiz et ve kullanıcının dilinde yanıt ver."},
            {"role": "user", "content": content}
        ]

        self.last_model_used = f"Qwen ({self.VISION_MODEL})"
        return self._call_api(messages, model=self.VISION_MODEL)

    def _transcribe_audio(self, video_path: str) -> str:
        """Videodan ses çıkar ve transkripsiyon yap."""
        import subprocess
        import tempfile

        try:
            import speech_recognition as sr
            from pydub import AudioSegment
        except ImportError:
            return ""

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_wav = tmp.name

        try:
            result = subprocess.run(
                ['ffmpeg', '-i', video_path, '-vn', '-acodec', 'pcm_s16le',
                 '-ar', '16000', '-ac', '1', '-y', tmp_wav],
                capture_output=True, text=True, timeout=60
            )

            if result.returncode != 0 or not os.path.exists(tmp_wav) or os.path.getsize(tmp_wav) < 100:
                return ""

            audio = AudioSegment.from_wav(tmp_wav)
            if len(audio) < 500:
                return ""

            recognizer = sr.Recognizer()
            full_text = []
            chunk_ms = 30000

            for i in range(0, len(audio), chunk_ms):
                chunk = audio[i:i + chunk_ms]
                chunk_path = tmp_wav + f'_chunk_{i}.wav'
                chunk.export(chunk_path, format='wav')

                try:
                    with sr.AudioFile(chunk_path) as source:
                        audio_data = recognizer.record(source)
                        try:
                            text = recognizer.recognize_google(audio_data, language='tr-TR')
                        except sr.UnknownValueError:
                            try:
                                text = recognizer.recognize_google(audio_data, language='en-US')
                            except sr.UnknownValueError:
                                text = ""
                        if text:
                            full_text.append(text)
                except Exception:
                    pass
                finally:
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)

            return ' '.join(full_text)
        finally:
            if os.path.exists(tmp_wav):
                os.remove(tmp_wav)

    @staticmethod
    def is_available() -> bool:
        """Qwen Free API sunucusunun erişilebilir olup olmadığını kontrol et."""
        try:
            r = requests.get(f"{QWEN_API_BASE}/status", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    @staticmethod
    def get_models() -> list:
        """Mevcut Qwen modellerinin listesini al."""
        try:
            r = requests.get(f"{QWEN_API_BASE}/models", timeout=5)
            if r.status_code == 200:
                data = r.json()
                if 'data' in data:
                    return [m['id'] for m in data['data']]
            return []
        except Exception:
            return []
