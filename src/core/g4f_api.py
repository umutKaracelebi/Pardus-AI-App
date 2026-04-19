"""
G4F API - Python'dan doğrudan GPT4Free kullanımı.
DeepInfra (Kimi K2.5) provider'ı üzerine yapılandırılmıştır.
"""
import os
import base64
import time
from g4f.client import Client
from g4f.Provider import DeepInfra

# --- Backward compatibility with Puter token logic ---
def has_token() -> bool:
    return True

def save_token(token: str):
    pass

def delete_token():
    pass
# -----------------------------------------------------

class G4FAPI:
    MODEL = "moonshotai/Kimi-K2.5"
    MAX_RETRIES = 3
    
    def __init__(self):
        # Explicit provider assignment via Client class avoids the ClientFactory formatting bugs
        self.client = Client(provider=DeepInfra)
        self.last_model_used = "Kimi K2.5 (DeepInfra)"
        
    def _call_with_retry(self, **kwargs):
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(**kwargs)
                return response.choices[0].message.content.strip()
            except Exception as e:
                err_str = str(e)
                if "Model busy" in err_str or "503" in err_str:
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(2)
                        continue
                raise Exception(f"G4F API (DeepInfra) hatası: {err_str}")
        
    def generate_response(self, messages: list) -> str:
        """Sohbet yanıtı üret."""
        system_prompt = (
            "Sen 'Pardus AI Asistanı' adında bir yapay zeka asistanısın. "
            "Pardus Linux için geliştirildin. Kimi K2.5 modelini kullanıyorsun."
        )
        
        # System prompt'unu ilk mesaja ekleyelim veya sisteme ayarlayalım.
        formatted_messages = [{"role": "system", "content": system_prompt}]
        
        # Mesaj formatı PollinationsAPI/PuterAPI'den geldiği için `content` liste veya string olabilir.
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if isinstance(content, list):
                # PuterAPI gibi davran ve text modüllerini birleştir
                text_parts = [item["text"] for item in content if item.get("type", "") == "text"]
                formatted_content = " ".join(text_parts)
            else:
                formatted_content = content
                
            formatted_messages.append({
                "role": role,
                "content": formatted_content
            })

        return self._call_with_retry(model=self.MODEL, messages=formatted_messages)

    def generate_vision_response(self, prompt: str, image_path: str) -> str:
        """Görsel analiz (vision) — base64 görsel + prompt."""
        if not os.path.exists(image_path):
            raise Exception(f"Görsel bulunamadı: {image_path}")

        try:
            with open(image_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()

            ext = os.path.splitext(image_path)[1].lower()
            mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}.get(ext, 'image/png')
            data_url = f"data:{mime};base64,{img_data}"

            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }]

            return self._call_with_retry(model=self.MODEL, messages=messages)
            
        except Exception as e:
            if "G4F API (DeepInfra)" in str(e):
                raise
            raise Exception(f"G4F Vision API hatası: {str(e)}")
            
    def generate_video_response(self, prompt: str, video_path: str) -> str:
        raise Exception("G4F API henüz video analizini desteklemiyor. Lütfen video yerine ekran görüntüsü kullanın.")
