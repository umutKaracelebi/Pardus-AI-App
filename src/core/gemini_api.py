import os
import google.generativeai as genai
from google.auth.transport.requests import Request
from src.core.gemini_oauth import GeminiOAuth
import PIL.Image

class GeminiAPI:
    def __init__(self):
        self.oauth_manager = GeminiOAuth()
        self.api_key_file = os.path.join(self.oauth_manager.config_dir, "gemini_api_key.txt")
        self.api_key = os.environ.get("GEMINI_API_KEY")
        
        if not self.api_key and os.path.exists(self.api_key_file):
            with open(self.api_key_file, "r") as f:
                self.api_key = f.read().strip()
        
    def is_authenticated(self):
        return self.api_key is not None or os.path.exists(self.oauth_manager.token_file)

    def generate_vision_response(self, text_prompt, image_path):
        """
        Runs the image and prompt through the google-generativeai SDK.
        Tries API Key first, then falls back to OAuth.
        """
        if self.api_key:
            genai.configure(api_key=self.api_key)
            print("☁️  Gemini AI Studio (API Key) üzerinden analiz yapılıyor...")
        else:
            creds = self.oauth_manager.get_credentials()
            if not creds:
                raise Exception("API Anahtarı bulunamadı ve OAuth girişi tamamlanamadı.")
                
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            
            genai.configure(credentials=creds)
            print("☁️  Gemini AI Studio (OAuth) üzerinden analiz yapılıyor...")
        
        # Load Model (gemini-1.5-flash supports vision and text on the free tier)
        model = genai.GenerativeModel('gemini-1.5-flash')
            
        try:
            import warnings
            warnings.filterwarnings("ignore") # Ignoredeprecation warning
            
            img = PIL.Image.open(image_path)
            response = model.generate_content([text_prompt, img])
            return response.text
        except Exception as e:
            raise Exception(f"Gemini Vision Hatası: {e}")
