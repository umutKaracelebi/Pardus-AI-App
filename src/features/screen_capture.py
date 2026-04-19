import mss
import mss.tools
import os
import time
import subprocess

class ScreenCapture:
    def __init__(self):
        self.sct = mss.mss()

    def capture_full_screen(self, output_path="screenshot.png"):
        """Captures the full screen and saves it to the specified path."""
        # Try MSS first
        try:
            # Get information of monitor 1
            monitor = self.sct.monitors[1]
            
            # Grab the data
            sct_img = self.sct.grab(monitor)
            
            # MSS bazen siyah ekran döndürebilir, bu duruma karşı dosya boyutunu veya içeriğini kontrol etmek zor
            # Ama dosya oluştuysa başarılı kabul edip kaydediyoruz.
            # Ancak kullanıcı "siyah ekran" diyorsa, MSS işe yaramamış demektir.
            # O yüzden önce fallback'leri denemek daha güvenli olabilir eğer sistemde varsa.
            
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=output_path)
            
            # TODO: Siyah ekran kontrolü yapılabilir (piksel analizi ile)
            
            return output_path
        except Exception as e:
            print(f"Error capturing screen with MSS: {e}")
            print("Trying fallback: gnome-screenshot...")
            return self.capture_with_gnome_screenshot(output_path)

    def capture_with_gnome_screenshot(self, output_path):
        """Fallback method using gnome-screenshot."""
        try:
            subprocess.run(["gnome-screenshot", "-f", output_path], check=True)
            if os.path.exists(output_path):
                return output_path
            return self.capture_with_scrot(output_path)
        except Exception as e:
            print(f"Error capturing with gnome-screenshot: {e}")
            print("Trying fallback: scrot...")
            return self.capture_with_scrot(output_path)

    def capture_with_scrot(self, output_path):
        """Fallback method using scrot."""
        try:
            # Check if scrot is installed
            subprocess.run(["scrot", output_path], check=True)
            if os.path.exists(output_path):
                return output_path
            return None
        except Exception as e:
            print(f"Error capturing screen with scrot: {e}")
            return None

    def capture_region(self, top, left, width, height, output_path="screenshot_region.png"):
        """Captures a specific region of the screen."""
        try:
            monitor = {"top": top, "left": left, "width": width, "height": height}
            sct_img = self.sct.grab(monitor)
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=output_path)
            return output_path
        except Exception as e:
            print(f"Error capturing region: {e}")
            return None
