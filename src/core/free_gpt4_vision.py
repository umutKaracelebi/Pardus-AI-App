import os
import base64
import re
import time
from openai import OpenAI

# Kimi K2.5 by Moonshot AI - open source
MODEL = "kimi"

API_KEY = "g4f_u_mmdc5u_2523f5069691205096c339d099fb0643137af55bc4e79b67_a55cf5ad"
BASE_URL = "https://g4f.space/v1"

# OpenRouter - ücretsiz açık kaynak modeller (limitsiz yedek)
OPENROUTER_KEY = ""
OPENROUTER_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS = [
    ("qwen/qwen3.6-plus:free", "Qwen 3.6 Plus"),
    ("nvidia/nemotron-3-super-120b-a12b:free", "Nemotron 120B"),
]


# Patterns to strip from responses (proxy ads)
_AD_PATTERNS = [
    r'\n*Need proxies cheaper than the market\?\s*\nhttps?://\S+\s*',
    r'\n*---\n*Need proxies.*$',
    r'\n*\*\*Need proxies.*$',
]

# AI identity replacements
_IDENTITY_REPLACEMENTS = [
    (r'[Bb]en\s+(?:ise\s+|bir\s+)?(?:Claude|GPT|Gemini|Kimi|ChatGPT|Copilot|DeepSeek|Llama|Mistral)\S*', 'tr'),
    (r'Claude\s+[\d.]+\s*\w*', 'tr'),
    (r'GPT-?[\d.]+\s*\w*', 'tr'),
    (r'Gemini\s+[\d.]+\s*\w*', 'tr'),
    (r"I(?:'m|\s+am)\s+(?:a\s+)?(?:Claude|GPT|Gemini|Kimi|ChatGPT|Copilot|DeepSeek)\S*", 'en'),
    (r'Anthropic\s+(?:şirketi\s+)?tarafından\s+\w+', 'company_tr'),
    (r'OpenAI\s+(?:şirketi\s+)?tarafından\s+\w+', 'company_tr'),
    (r'Moonshot\s*AI?\s+tarafından\s+\w+', 'company_tr'),
    (r'Google\s+(?:şirketi\s+)?tarafından\s+\w+', 'company_tr'),
    (r'(?:made|created|developed|built)\s+by\s+(?:Anthropic|OpenAI|Moonshot|Google|Meta)', 'company_en'),
    (r'[Ss]izinle\s+konuşan\s+model\s+\S+(?:\s+[\d.]+\s*\w*)?', 'model_ref_tr'),
    (r'[Kk]onuşan\s+model\s+\S+', 'model_ref_tr'),
]

def _clean_response(text: str, model_name: str = "") -> str:
    for pattern in _AD_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    
    mn = model_name or "açık kaynak"
    replacements = {
        'tr': f'Ben Pardus AI Asistanıyım ({mn} modeli üzerinde çalışıyorum)',
        'en': f'I am Pardus AI Assistant (powered by {mn} model)',
        'company_tr': 'Pardus ekibi tarafından geliştirilmiş',
        'company_en': 'developed for Pardus Linux',
        'model_ref_tr': f'Pardus AI Asistanı ({mn})',
    }
    
    for pattern, tag in _IDENTITY_REPLACEMENTS:
        text = re.sub(pattern, replacements.get(tag, replacements['tr']), text)
    
    return text.rstrip()


class FreeGPT4Vision:
    """Vision: Kimi K2.5 (birincil) → OpenRouter/Qwen+Nemotron (limitsiz yedek)."""

    def __init__(self):
        self.client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL
        )
        self.openrouter = OpenAI(
            api_key=OPENROUTER_KEY,
            base_url=OPENROUTER_URL
        )
        self.last_model_used = ""

    def _prepare_image(self, image_path):
        """Resim dosyasını base64 data URL'ye çevir."""
        if not os.path.exists(image_path):
            raise Exception(f"Resim dosyası bulunamadı: {image_path}")

        with open(image_path, "rb") as f:
            img_data = f.read()

        ext = os.path.splitext(image_path)[1].lower()
        mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp'}
        mime_type = mime_map.get(ext, 'image/jpeg')
        b64 = base64.b64encode(img_data).decode('utf-8')
        return f"data:{mime_type};base64,{b64}"

    def generate_vision_response(self, text_prompt: str, image_path: str) -> str:
        import random

        data_url = self._prepare_image(image_path)
        nonce = f"[sid:{random.randint(10000,99999)}-t:{int(time.time())}]"
        unique_prompt = f"{text_prompt}\n{nonce}"

        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": unique_prompt},
                {"type": "image_url", "image_url": {"url": data_url}}
            ]
        }]

        # ── 1) BİRİNCİL: Kimi K2.5 (Moonshot AI, açık kaynak) ──
        rate_limited = False
        for attempt in range(2):
            try:
                if attempt > 0:
                    time.sleep(2)
                print("☁️  Kimi K2.5 ile analiz yapılıyor...")
                response = self.client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    temperature=1.0
                )
                result = _clean_response(response.choices[0].message.content.strip(), "Kimi K2.5")
                if result and len(result) > 3:
                    print("   ✅ Kimi K2.5 başarılı.")
                    self.last_model_used = "Kimi K2.5"
                    return result
            except Exception as e:
                err = str(e)
                print(f"[Pardus AI] Kimi hatası (deneme {attempt+1}): {err[:120]}")
                if "429" in err or "rate_limit" in err.lower():
                    rate_limited = True
                    break

        # ── 2) YEDEK: OpenRouter ücretsiz açık kaynak modeller (limitsiz) ──
        if rate_limited:
            for model_id, model_name in OPENROUTER_MODELS:
                try:
                    print(f"☁️  OpenRouter/{model_name} ile analiz yapılıyor (limitsiz)...")
                    response = self.openrouter.chat.completions.create(
                        model=model_id,
                        messages=messages,
                        temperature=1.0
                    )
                    if response and response.choices and response.choices[0].message.content:
                        result = _clean_response(response.choices[0].message.content.strip(), model_name)
                        if result and len(result) > 3:
                            print(f"   ✅ {model_name} başarılı.")
                            self.last_model_used = model_name
                            return result
                except Exception as e:
                    print(f"[Pardus AI] {model_name} hatası: {str(e)[:120]}")

        raise Exception("AI yanıt veremedi. Lütfen biraz bekleyip tekrar deneyin.")

    def generate_video_response(self, text_prompt: str, video_path: str, frame_interval: float = 3.0) -> str:
        """Analyze a video by extracting frames every N seconds and transcribing audio."""
        import cv2

        print("🎬 Video analiz ediliyor...")

        if not os.path.exists(video_path):
            raise Exception(f"Video dosyası bulunamadı: {video_path}")

        # ── 1. Extract frames every frame_interval seconds ──
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("Video dosyası açılamadı. Desteklenen formatlar: mp4, avi, mkv, webm, mov")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        duration = total_frames / fps if fps > 0 else 0

        if total_frames < 1:
            cap.release()
            raise Exception("Video dosyasından kare okunamadı.")

        # Calculate frame indices at every frame_interval seconds
        frame_indices = []
        t = 0.0
        while t < duration:
            frame_idx = int(t * fps)
            if frame_idx < total_frames:
                frame_indices.append((frame_idx, t))
            t += frame_interval
        # Always include last frame
        last_t = duration - 0.1
        if last_t > 0 and (not frame_indices or frame_indices[-1][1] < last_t - 1):
            frame_indices.append((total_frames - 1, duration))

        frames_b64 = []
        frame_times = []
        for idx, t in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                b64 = base64.b64encode(buf.tobytes()).decode('utf-8')
                frames_b64.append(b64)
                frame_times.append(t)
        cap.release()

        if not frames_b64:
            raise Exception("Videodan kare çıkarılamadı.")

        print(f"   → {len(frames_b64)} kare çıkarıldı (süre: {duration:.1f}s, her {frame_interval}s'de bir)")

        # ── 2. Audio analysis: speech transcription + sound classification ──
        audio_transcript = ""
        audio_description = ""
        
        # Speech transcription
        try:
            audio_transcript = self._transcribe_audio(video_path)
            if audio_transcript:
                print(f"   → Ses transkripsiyonu alındı ({len(audio_transcript)} karakter)")
        except Exception as e:
            print(f"   → Ses transkripsiyon hatası: {str(e)[:60]}")

        # Sound classification with librosa
        try:
            from src.core.audio_analyzer import analyze_audio
            audio_result = analyze_audio(video_path)
            if audio_result['has_audio'] and audio_result['description']:
                audio_description = audio_result['description']
                print(f"   → Ses sınıflandırması tamamlandı: {audio_description[:80]}...")
            elif not audio_result['has_audio']:
                print("   → Videoda ses bulunamadı.")
        except Exception as e:
            print(f"   → Ses sınıflandırma hatası: {str(e)[:80]}")

        # ── 3. Build multi-image message with timestamps + audio ──
        time_info = ', '.join([f"Kare {i+1}: {t:.1f}s" for i, t in enumerate(frame_times)])
        
        prompt_parts = [
            f"Bu bir videodan her {frame_interval:.0f} saniyede bir çıkarılmış {len(frames_b64)} karedir.",
            f"Video süresi: {duration:.1f} saniye.",
            f"Karelerin zamanları: {time_info}."
        ]
        
        if audio_transcript:
            prompt_parts.append(f"\nVideodaki konuşma transkripsiyonu:\n\"{audio_transcript}\"")
        
        if audio_description:
            prompt_parts.append(f"\nSes analizi sonuçları:\n{audio_description}")
        
        if not audio_transcript and not audio_description:
            prompt_parts.append("\nVideoda ses tespit edilemedi.")
        
        prompt_parts.append(text_prompt)
        
        # Cache-busting nonce
        import random
        nonce = f"[sid:{random.randint(10000,99999)}-t:{int(time.time())}]"
        
        content = [{"type": "text", "text": " ".join(prompt_parts) + f"\n{nonce}"}]
        for b64 in frames_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })

        messages = [{"role": "user", "content": content}]

        for attempt in range(3):
            try:
                if attempt > 0:
                    time.sleep(3)
                response = self.client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    temperature=1.2
                )
                result = _clean_response(response.choices[0].message.content.strip())
                if result and len(result) > 3:
                    return result
            except Exception as e:
                err_msg = str(e)
                print(f"[Pardus AI] Video analiz hatası (deneme {attempt + 1}): {err_msg[:120]}")
                if attempt == 2:
                    raise Exception(f"Video analizi başarısız: {err_msg[:200]}")

        raise Exception("Video analiz sağlayıcısı yanıt vermedi. Tekrar deneyin.")

    def _transcribe_audio(self, video_path: str) -> str:
        """Extract audio from video and transcribe it using Google Speech Recognition."""
        import subprocess
        import tempfile
        import speech_recognition as sr
        from pydub import AudioSegment

        # Extract audio from video using ffmpeg
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

            # Split audio into 30-second chunks for better recognition
            audio = AudioSegment.from_wav(tmp_wav)
            if len(audio) < 500:  # Less than 0.5 second
                return ""

            recognizer = sr.Recognizer()
            full_text = []
            chunk_ms = 30000  # 30 seconds per chunk

            for i in range(0, len(audio), chunk_ms):
                chunk = audio[i:i + chunk_ms]
                chunk_path = tmp_wav + f'_chunk_{i}.wav'
                chunk.export(chunk_path, format='wav')
                
                try:
                    with sr.AudioFile(chunk_path) as source:
                        audio_data = recognizer.record(source)
                        # Try Turkish first, then English
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
