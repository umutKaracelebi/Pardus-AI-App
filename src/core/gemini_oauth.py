import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

class GeminiOAuth:
    def __init__(self):
        self.config_dir = os.path.expanduser("~/.config/pardus_ai")
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Scopes required to use the Gemini API (Cloud AI Studio)
        # Note: Since there isn't a direct "Gemini API" scope for consumer endpoints yet via pure OAuth in some cases,
        # usually Cloud AI uses the general cloud-platform scope if using Vertex, 
        # BUT for MakerSuite/AI Studio 'google-genai', the credentials just need to be valid user credentials.
        # Actually, AI Studio does not easily support pure OAuth for consumer endpoints without a GCP project.
        # However, the user explicitly requested OAuth. 
        # The standard scope for Gemini API is:
        self.scopes = [
            "https://www.googleapis.com/auth/generative-language",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ]
        
        self.client_secret_file = os.path.join(self.config_dir, "oauth_client_secret.json")
        self.token_file = os.path.join(self.config_dir, "google_oauth_token.json")

    def get_credentials(self):
        creds = None
        # The file token.json stores the user's access and refresh tokens
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
            except Exception as e:
                print(f"Eski token okunamadı, yeniden giriş yapılacak: {e}")

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Token yenileme başarısız oldu, manuel giriş gerekecek: {e}")
                    creds = self._run_auth_flow()
            else:
                creds = self._run_auth_flow()
                
            if creds:
                # Save the credentials for the next run
                with open(self.token_file, "w") as token:
                    token.write(creds.to_json())

        return creds
        
    def _run_auth_flow(self):
        if not os.path.exists(self.client_secret_file):
            self._print_setup_instructions()
            return None
            
        try:
            print("\n🌐 Tarayıcınızda Google Giriş sayfası açılıyor...")
            flow = InstalledAppFlow.from_client_secrets_file(
                self.client_secret_file, self.scopes
            )
            # Run local server to catch the callback
            creds = flow.run_local_server(port=0)
            return creds
        except Exception as e:
            print(f"\n❌ OAuth Hatası: {e}")
            return None

    def _print_setup_instructions(self):
        print("\n" + "="*60)
        print("⚠️  Google OAuth Client ID Dosyası Eksik!")
        print("Resmi (ücretsiz) güvenli giriş yapabilmeniz için Google Cloud üzerinden bir izin dosyası oluşturmanız gerekmektedir:\n")
        print("1. https://console.cloud.google.com/ adresine gidin ve yeni bir proje oluşturun.")
        print("2. 'APIs & Services' -> 'Credentials' (Kimlik Bilgileri) sayfasına gidin.")
        print("3. 'Create Credentials' -> 'OAuth client ID' seçin.")
        print("4. Application type: 'Desktop app' (Masaüstü uygulaması) seçin.")
        print("5. Oluşturduktan sonra 'Download JSON' butonuna tıklayarak dosyayı indirin.")
        print(f"6. İndirdiğiniz dosyayı şu isimle kaydedin: {self.client_secret_file}")
        print("="*60 + "\n")
