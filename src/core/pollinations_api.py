import re
import time
from openai import OpenAI

# Kimi K2.5 by Moonshot AI - open source, supports text + vision
MODEL = "kimi"
MODEL_DISPLAY = "Kimi K2.5"  # Kullanıcıya gösterilecek model adı

API_KEY = "g4f_u_mmdc5u_2523f5069691205096c339d099fb0643137af55bc4e79b67_a55cf5ad"
BASE_URL = "https://g4f.space/v1"


# Patterns to strip from api.airforce responses (proxy ads)
_AD_PATTERNS = [
    r'\n*Need proxies cheaper than the market\?\s*\nhttps?://\S+\s*',
    r'\n*---\n*Need proxies.*$',
    r'\n*\*\*Need proxies.*$',
]

# AI identity replacements - prevent proxy model from leaking its real name
_IDENTITY_REPLACEMENTS = [
    # Turkish - tüm varyasyonlar (ise, bir, de, um, ım, yım)
    (r'[Bb]en\s+(?:ise\s+|bir\s+)?(?:Claude|GPT|Gemini|Kimi|ChatGPT|Copilot|DeepSeek|Llama|Mistral)\S*', 'tr'),
    # "Claude 3.5 Sonnet" gibi model adları
    (r'Claude\s+[\d.]+\s*\w*', 'tr'),
    (r'GPT-?[\d.]+\s*\w*', 'tr'),
    (r'Gemini\s+[\d.]+\s*\w*', 'tr'),
    # English
    (r"I(?:'m|\s+am)\s+(?:a\s+)?(?:Claude|GPT|Gemini|Kimi|ChatGPT|Copilot|DeepSeek)\S*", 'en'),
    # Şirket referansları - Türkçe
    (r'Anthropic\s+(?:şirketi\s+)?tarafından\s+\w+', 'company_tr'),
    (r'OpenAI\s+(?:şirketi\s+)?tarafından\s+\w+', 'company_tr'),
    (r'Moonshot\s*AI?\s+tarafından\s+\w+', 'company_tr'),
    (r'Google\s+(?:şirketi\s+)?tarafından\s+\w+', 'company_tr'),
    # Şirket referansları - English
    (r'(?:made|created|developed|built)\s+by\s+(?:Anthropic|OpenAI|Moonshot|Google|Meta)', 'company_en'),
    # "Şu an sizinle konuşan model Claude 3.5 Sonnet" gibi cümleler
    (r'[Ss]izinle\s+konuşan\s+model\s+\S+(?:\s+[\d.]+\s*\w*)?', 'model_ref_tr'),
    (r'[Kk]onuşan\s+model\s+\S+', 'model_ref_tr'),
]

def _clean_response(text: str) -> str:
    """Remove ad spam and fix AI identity leaks."""
    for pattern in _AD_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    
    identity_tr = f'Ben Pardus AI Asistanıyım ({MODEL_DISPLAY} açık kaynak modeli üzerinde çalışıyorum)'
    identity_en = f'I am Pardus AI Assistant (powered by {MODEL_DISPLAY} open source model)'
    company_tr = 'Pardus ekibi tarafından geliştirilmiş'
    company_en = 'developed for Pardus Linux'
    model_ref = f'Pardus AI Asistanı ({MODEL_DISPLAY})'
    
    replacements = {
        'tr': identity_tr,
        'en': identity_en,
        'company_tr': company_tr,
        'company_en': company_en,
        'model_ref_tr': model_ref,
    }
    
    for pattern, tag in _IDENTITY_REPLACEMENTS:
        replacement = replacements.get(tag, identity_tr)
        text = re.sub(pattern, replacement, text)
    
    return text.rstrip()


class PollinationsAPI:
    """Text chat using g4f.space API with OpenAI-compatible client."""

    def __init__(self):
        self.client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL
        )
        # Pollinations doğrudan API - KEY YOK, limitsiz
        self.pollinations_direct = OpenAI(
            api_key='dummy',
            base_url='https://text.pollinations.ai/openai'
        )

    def generate_response(self, messages):
        simple_messages = [
            {"role": "system", "content": f"Sen 'Pardus AI Asistanı' adında bir yapay zeka asistanısın. Pardus Linux için geliştirildin. Arkada {MODEL_DISPLAY} açık kaynak modelini kullanıyorsun. Biri sana hangi model olduğunu sorarsa 'Ben Pardus AI Asistanıyım, {MODEL_DISPLAY} açık kaynak modeli üzerinde çalışıyorum' de. Kullanıcının yazdığı dilde yanıt ver. En iyi ve en detaylı yanıtı vermeye çalış."}
        ]

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

        # ── 1) BİRİNCİL: Pollinations doğrudan (KEY YOK, LİMİTSİZ) ──
        try:
            print("☁️  Pollinations (limitsiz) ile yanıt oluşturuluyor...")
            response = self.pollinations_direct.chat.completions.create(
                model='openai',
                messages=simple_messages,
                temperature=0.9
            )
            result = _clean_response(response.choices[0].message.content)
            if result and len(result) > 3:
                print("   ✅ Pollinations başarılı (limitsiz).")
                return result
        except Exception as e:
            print(f"[Pardus AI] Pollinations hatası: {str(e)[:120]}")

        # ── 2) YEDEK: Kimi K2.5 (g4f.space, açık kaynak) ──
        for attempt in range(2):
            try:
                if attempt > 0:
                    time.sleep(2)
                print("☁️  Kimi K2.5 ile yanıt oluşturuluyor (yedek)...")
                response = self.client.chat.completions.create(
                    model=MODEL,
                    messages=simple_messages,
                    temperature=0.9
                )
                result = _clean_response(response.choices[0].message.content)
                if result and len(result) > 3:
                    return result
            except Exception as e:
                print(f"[Pardus AI] Kimi hatası (deneme {attempt+1}): {str(e)[:120]}")

        raise Exception("AI yanıt veremedi. Lütfen tekrar deneyin.")
