import time
import shutil
import subprocess
from evdev import UInput, ecodes

print("Lütfen bir arama kutusuna veya metin editörüne tıklayın. 5 saniye içinde yazı yazılacak...")
time.sleep(5)

# 1. Sanal Klavye Oluştur
cap_kbd = {
    ecodes.EV_KEY: [
        ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL, ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT,
        ecodes.KEY_V, ecodes.KEY_C, ecodes.KEY_X, ecodes.KEY_ENTER, ecodes.KEY_BACKSPACE, ecodes.KEY_ESC,
        ecodes.KEY_A, ecodes.KEY_S, ecodes.KEY_D, ecodes.KEY_F, ecodes.KEY_G, ecodes.KEY_H, ecodes.KEY_J, 
        ecodes.KEY_K, ecodes.KEY_L, ecodes.KEY_Z, ecodes.KEY_X, ecodes.KEY_C, ecodes.KEY_V, ecodes.KEY_B, 
        ecodes.KEY_N, ecodes.KEY_M, ecodes.KEY_Q, ecodes.KEY_W, ecodes.KEY_E, ecodes.KEY_R, ecodes.KEY_T, 
        ecodes.KEY_Y, ecodes.KEY_U, ecodes.KEY_I, ecodes.KEY_O, ecodes.KEY_P,
        ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4, ecodes.KEY_5,
        ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8, ecodes.KEY_9, ecodes.KEY_0
    ]
}

try:
    keyboard = UInput(events=cap_kbd, name='Virtual Keyboard Test')
    time.sleep(1) # Sistemin klavyeyi tanıması için
except Exception as e:
    print("Sanal klavye oluşturulamadı! (sudo yetkisi gerekebilir):", e)
    exit(1)

text = "TEST YAZISI 123"

# 2. Pano
if shutil.which("wl-copy"):
    subprocess.run(["wl-copy"], input=text.encode('utf-8'))
    print("wl-copy ile panoya kopyalandı.")
elif shutil.which("xclip"):
    subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode('utf-8'))
    print("xclip ile panoya kopyalandı.")

time.sleep(0.5)

# 3. Ctrl+V Gönder
print("Ctrl+V gönderiliyor...")
keyboard.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 1)
keyboard.syn()
time.sleep(0.05)

keyboard.write(ecodes.EV_KEY, ecodes.KEY_V, 1)
keyboard.syn()
time.sleep(0.05)

keyboard.write(ecodes.EV_KEY, ecodes.KEY_V, 0)
keyboard.syn()
time.sleep(0.05)

keyboard.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 0)
keyboard.syn()

print("İşlem bitti. Yazı eklendi mi kontrol edin!")
keyboard.close()
