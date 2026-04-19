import os
import time
import pyautogui
from termcolor import colored

class ScreenUtils:
    def __init__(self, save_dir="screenshots"):
        self.save_dir = save_dir
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

    def take_screenshot(self, filename=None):
        """
        Ekran görüntüsü alır ve kaydeder.
        """
        if not filename:
            filename = f"screenshot_{int(time.time())}.png"
        
        filepath = os.path.join(self.save_dir, filename)
        
        try:
            print(colored("📸 Ekran görüntüsü alınıyor...", "cyan"))
            # Sadece ana ekranı çek
            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)
            print(colored(f"✅ Kaydedildi: {filepath}", "green"))
            return filepath
        except Exception as e:
            print(colored(f"❌ Hata: Ekran görüntüsü alınamadı -> {str(e)}", "red"))
            return None
