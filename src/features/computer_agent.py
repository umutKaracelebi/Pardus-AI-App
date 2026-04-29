"""
Computer Agent — AI kontrolünde bilgisayarı otonom kullanma modülü.
Ekran görüntüsü alır → Vision AI'ya gönderir → Gelen aksiyonu çalıştırır → Döngü.

Wayland uyumlu: evdev/uinput ile mouse, xdotool ile klavye kontrolü.
"""
import os
import json
import time
import threading
import re
import subprocess
from enum import Enum


class AgentState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_USER = "waiting_user"
    PAUSED = "paused"
    DONE = "done"
    ERROR = "error"


AGENT_SYSTEM_PROMPT = """Sen bir Pardus Linux masaüstü kontrol ajanısın. Kullanıcının verdiği görevi tamamlamak için bilgisayarı kontrol edeceksin.

Her adımda sana ekranın görüntüsü gönderilecek. Yapılması gereken SONRAKİ aksiyonu JSON formatında dön.

AKSİYONLAR:
1. Tıklama: {"action": "click", "element_id": 12, "thought": "..."}
2. Tıkla ve yaz: {"action": "click", "element_id": 12, "text": "yazılacak metin", "thought": "..."}
3. Koordinat ile tıkla (element numaralanmamışsa): {"action": "click", "x": 525, "y": 400, "thought": "..."}
4. Çift tıklama: {"action": "double_click", "element_id": 12, "thought": "..."}
5. Sağ tıklama: {"action": "right_click", "element_id": 12, "thought": "..."}
6. Kısayol tuşu: {"action": "hotkey", "keys": ["ctrl", "c"], "thought": "..."}
7. Tek tuş basma: {"action": "press_key", "key": "enter", "thought": "..."}
8. Kaydırma: {"action": "scroll", "direction": "down", "amount": 3, "thought": "..."}
9. Bekleme: {"action": "wait", "seconds": 2, "thought": "..."}
10. Görev tamamlandı: {"action": "done", "summary": "Ne yapıldığının özeti", "thought": "..."}

Ekran çözünürlüğü: 1366x768 piksel. x,y koordinatları bu aralıkta olmalı.

KOORDİNAT KURALLARI:
- Ekrandaki tıklanabilir öğelerin etrafı YEŞİL KUTULARLA çevrilmiş ve yanlarına SARI NUMARALAR [1], [2], [3] eklenmiştir.
- Tıklamak istediğin öğenin SARI NUMARASINI bul ve "element_id" olarak gönder.
- Öncelikle element_id kullan. Eğer tıklamak istediğin alan numaralanmamışsa (yeşil kutu yoksa), x ve y koordinatlarını tahmin edebilirsin:
  {"action": "click", "x": 525, "y": 400, "thought": "Numaralanmamış kart alanına tıklıyorum"}
- Büyük bir yeşil kutu [12] gibi bir alanın İÇİNDE daha küçük tıklanabilir öğeler olabilir. Kartın sol tarafına tıklamak için x,y kullan.

YAZI YAZMA:
- Bir metin alanına yazı yazman gerekiyorsa click aksiyonuna "text" alanı ekle.
- Örnek: {"action": "click", "element_id": 9, "text": "merhaba dünya", "thought": "Arama kutusuna yazıyorum"}

GÖREV TAMAMLAMA:
- Her adımda ekrana bak ve görevin tamamlanıp tamamlanmadığını değerlendir.
- Tamamlandıysa hemen done dön. Aynı şeyi tekrar yapma.
- Görevde birden fazla adım varsa (örn: "X aç ve Y yap"), X tamamlandıysa Y'ye geç. X'i tekrar yapma.
- Bir uygulama zaten açıksa, onu tekrar aramaya ÇALIŞMA. Uygulama içinde görevin geri kalanına devam et.
- "Pardus Mağaza" veya "Yazılım Merkezi" açıksa, arama kutusuna "yazılım merkezi" YAZMA. Doğrudan uygulama içinde çalış.
- Aynı element_id'ye arka arkaya 2 kez tıkladıysan, ekran değişmemiş demektir. Farklı bir element dene.
- "Yükle", "İndir", "Kur" gibi bir butona bastıktan sonra {"action": "wait", "seconds": 3} gönder.
- BİR TANE indirme/yükleme başlattıktan sonra HEMEN done dön. Birden fazla şey indirme!
- Uygulama açtıktan sonra {"action": "wait", "seconds": 3} gönder ki uygulama tam yüklensin.
- Firefox açıldıktan sonra arama yapmak için ana sayfadaki "Web'de ara" kutusuna tıklayıp yaz, sonra Enter bas.

UYGULAMA AÇMA (ÇOK ÖNEMLİ!):
- Dock bar'daki ikonlara ASLA tıklama. Dock'taki hiçbir öğeye tıklama.
- Uygulama açmak için İLK ADIM OLARAK: {"action": "hotkey", "keys": ["super"]} gönder.
- DİKKAT: Super tuşu toggle'dır! Bir kez basınca menü açılır, tekrar basınca KAPANIR. Super'e sadece 1 KEZ bas.
- Açılan ekranda üstte "Yazarak ara" kutusu var. O kutuya TIKLA ve uygulamanın DOĞRU ADINI YAZ:
  {"action": "click", "element_id": 1, "text": "firefox", "thought": "Arama kutusuna yazıyorum"}
- Activities ekranındaki uygulama grid'ine (ikonlara) DOĞRUDAN TIKLAMAK YERİNE, HER ZAMAN arama kutusuna uygulamanın adını yaz.
- LibreOffice uygulamaları açarken DOĞRU İSİM yaz: "writer" (metin), "calc" (hesap tablosu), "impress" (sunum). Sadece "libreoffice" yazma.
- Arama sonucunda çıkan uygulama ikonuna tıkla.
- Uygulama açıldıktan sonra Super'e bir daha BASMA. Uygulama içinde çalışmaya devam et.

GENEL KURALLAR:
- Her yanıtta SADECE TEK BİR JSON nesnesi dön, başka hiçbir şey yazma.
- "thought" alanında ne gördüğünü ve neden bu aksiyonu seçtiğini KISA tut (en fazla 2 cümle).
- Kararı kendin ver, otonom çalış.
- element_id her zaman TAM SAYI (integer) olmalı, ASLA liste yazma. Doğru: "element_id": 2  Yanlış: "element_id": [2]
- Masaüstündeki ikonları ve klasörleri açmak için ÇİFT TIKLAMA kullan: {"action": "double_click", "element_id": 2}
- Dosya yöneticisinde klasör açmak için de ÇİFT TIKLAMA gerekir.
- Aynı element_id'ye arka arkaya 2 kez tıklama! Tıkladıysan ve ekran değişmediyse farklı bir strateji dene.
- Bir butona tıkladın ve "Kaydet" / "Save" diyalogu açıldıysa → Enter bas: {"action": "press_key", "key": "enter", "thought": "Kaydet diyalogu onaylanıyor"}
- İndirme linki veya butonu tıkladığında indirme başladıysa → done de.
"""



# ──────────────── Wayland-uyumlu Input Controller ────────────────

class WaylandInputController:
    """evdev/uinput absolute pointer + wtype keyboard for Wayland GNOME.
    Uses 0-65535 scaled ABS coordinates to bypass GNOME's resolution-mapped restrictions."""

    def __init__(self, screen_w=1366, screen_h=768):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._pointer = None   # Absolute pointer
        self._scroll = None    # Scroll wheel device
        self._env = {**os.environ, 'DISPLAY': ':0'}
        import shutil
        self.has_wtype = shutil.which("wtype") is not None

    def _ensure_pointer(self):
        if self._pointer is None:
            self._fix_uinput_permissions()
            from evdev import UInput, ecodes, AbsInfo
            
            # 1. Absolute Pointer (Sadece ABS ve KEY, REL eklenirse GNOME Wayland bu cihazı çöpe atıyor)
            cap_ptr = {
                ecodes.EV_ABS: [
                    (ecodes.ABS_X, AbsInfo(value=0, min=0, max=65535, fuzz=0, flat=0, resolution=0)),
                    (ecodes.ABS_Y, AbsInfo(value=0, min=0, max=65535, fuzz=0, flat=0, resolution=0)),
                ],
                ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE, ecodes.BTN_TOUCH]
            }
            self._pointer = UInput(events=cap_ptr, name='Virtual Absolute Pointer', input_props=[ecodes.INPUT_PROP_DIRECT])
            
            # 2. Standart Fare Cihazı (Tekerlek ve İmleci Görünür Kılmak İçin)
            cap_scroll = {
                ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL],
                ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE]
            }
            self._scroll = UInput(events=cap_scroll, name='Virtual Scroll Wheel')
            
            # 3. Sanal Klavye (Tüm tuşları ekleyerek GNOME'un reddetmesini önlüyoruz)
            cap_kbd = {
                ecodes.EV_KEY: [
                    ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL, ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT,
                    ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT, ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA,
                    ecodes.KEY_V, ecodes.KEY_C, ecodes.KEY_X, ecodes.KEY_ENTER, ecodes.KEY_BACKSPACE, ecodes.KEY_ESC,
                    ecodes.KEY_UP, ecodes.KEY_DOWN, ecodes.KEY_LEFT, ecodes.KEY_RIGHT, ecodes.KEY_SPACE, ecodes.KEY_TAB,
                    ecodes.KEY_DELETE, ecodes.KEY_HOME, ecodes.KEY_END,
                    ecodes.KEY_F1, ecodes.KEY_F2, ecodes.KEY_F3, ecodes.KEY_F4, ecodes.KEY_F5,
                    ecodes.KEY_F6, ecodes.KEY_F7, ecodes.KEY_F8, ecodes.KEY_F9, ecodes.KEY_F10,
                    ecodes.KEY_F11, ecodes.KEY_F12,
                    ecodes.KEY_Q, ecodes.KEY_W, ecodes.KEY_E, ecodes.KEY_R, ecodes.KEY_T, ecodes.KEY_Y, ecodes.KEY_U,
                    ecodes.KEY_I, ecodes.KEY_O, ecodes.KEY_P, ecodes.KEY_A, ecodes.KEY_S, ecodes.KEY_D, ecodes.KEY_F,
                    ecodes.KEY_G, ecodes.KEY_H, ecodes.KEY_J, ecodes.KEY_K, ecodes.KEY_L, ecodes.KEY_Z, ecodes.KEY_X,
                    ecodes.KEY_C, ecodes.KEY_V, ecodes.KEY_B, ecodes.KEY_N, ecodes.KEY_M,
                    ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4, ecodes.KEY_5,
                    ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8, ecodes.KEY_9, ecodes.KEY_0,
                    ecodes.KEY_MINUS, ecodes.KEY_EQUAL, ecodes.KEY_DOT, ecodes.KEY_COMMA, ecodes.KEY_SLASH,
                ]
            }
            self._keyboard = UInput(events=cap_kbd, name='Virtual Keyboard')
            
            print("[Agent] Wayland uyumlu Fare ve Klavye donanımları oluşturuldu...")
            time.sleep(2.0)

    def _fix_uinput_permissions(self):
        try:
            if os.access('/dev/uinput', os.W_OK):
                return
        except Exception:
            pass
        print("[Agent] ⚠️ /dev/uinput yazma izni yok, düzeltiliyor...")
        try:
            subprocess.run(
                ['pkexec', 'sh', '-c', 'chmod 660 /dev/uinput && chown root:input /dev/uinput'],
                timeout=30
            )
        except Exception as e:
            print(f"[Agent] ❌ uinput izin hatası: {e}")

    def move_to(self, x, y):
        """Gerçek piksel koordinatını (0-1366) Wayland evrensel ölçeğine (0-65535) çevirip ışınlar."""
        from evdev import ecodes
        self._ensure_pointer()
        
        # Ekranın dışına çıkmasını engelle
        x = max(0, min(int(x), self.screen_w - 1))
        y = max(0, min(int(y), self.screen_h - 1))
        
        # 0-65535 aralığına oranla
        abs_x = int((x / self.screen_w) * 65535)
        abs_y = int((y / self.screen_h) * 65535)
        
        self._pointer.write(ecodes.EV_ABS, ecodes.ABS_X, abs_x)
        self._pointer.write(ecodes.EV_ABS, ecodes.ABS_Y, abs_y)
        self._pointer.syn()
        time.sleep(0.05)
        
        # İmleci GÖRÜNÜR KILMAK (Wake up) - Sadece hareket ettiğinde de imleç kayboluyordu
        if self._scroll:
            self._scroll.write(ecodes.EV_REL, ecodes.REL_X, 1)
            self._scroll.syn()
            time.sleep(0.01)
            self._scroll.write(ecodes.EV_REL, ecodes.REL_X, -1)
            self._scroll.syn()

    def click(self, x, y, button="left"):
        from evdev import ecodes
        self._ensure_pointer()
        self.move_to(x, y)
        time.sleep(0.1)
        btn = ecodes.BTN_LEFT if button == "left" else ecodes.BTN_RIGHT if button == "right" else ecodes.BTN_MIDDLE
        
        # GNOME'un absolute pointer'ı fare tıklaması olarak kabul etmesi için BTN_TOUCH sinyaline de ihtiyacı vardır
        self._pointer.write(ecodes.EV_KEY, ecodes.BTN_TOUCH, 1)
        self._pointer.write(ecodes.EV_KEY, btn, 1)
        self._pointer.syn()
        
        time.sleep(0.08)
        
        self._pointer.write(ecodes.EV_KEY, btn, 0)
        self._pointer.write(ecodes.EV_KEY, ecodes.BTN_TOUCH, 0)
        self._pointer.syn()
        
        # İmleci GÖRÜNÜR KILMAK (Wake up)
        # Wayland tablet/dokunmatik tıklamalarında imleci gizler. Standart faremizle 1 piksel oynatıp imleci geri getiriyoruz.
        self._scroll.write(ecodes.EV_REL, ecodes.REL_X, 1)
        self._scroll.syn()
        time.sleep(0.01)
        self._scroll.write(ecodes.EV_REL, ecodes.REL_X, -1)
        self._scroll.syn()

    def double_click(self, x, y):
        self.click(x, y)
        time.sleep(0.08)
        # İkinci tıklama — move_to tekrar gerekli çünkü birinci click cursor'ı oynatıyor
        self.click(x, y)

    def scroll(self, direction="down", amount=3):
        from evdev import ecodes
        self._ensure_pointer()
        val = amount if direction == "up" else -amount
        self._scroll.write(ecodes.EV_REL, ecodes.REL_WHEEL, val)
        self._scroll.syn()

    # ── Klavye (Evdev Virtual Keyboard + Clipboard Hack) ──
    # Wayland'de xdotool çalışmaz, wtype ise her uygulamaya (örn: Chrome) basamayabilir.
    # Çözüm: Metni panoya kopyalayıp donanımsal klavyeden "Ctrl+V" sinyali göndermek!
    
    def _set_clipboard(self, text):
        import subprocess, shutil
        
        # Wayland environment
        env = os.environ.copy()
        env.setdefault("WAYLAND_DISPLAY", "wayland-0")
        env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        
        # wl-copy dene
        if shutil.which("wl-copy"):
            try:
                subprocess.run(["wl-copy", "--type", "text/plain"], 
                             input=text.encode('utf-8'), env=env, timeout=2, 
                             capture_output=True, check=True)
                print(f"[Agent] Panoya kopyalandı (wl-copy): '{text[:50]}'")
                return
            except Exception as e:
                print(f"[Agent] wl-copy başarısız: {e}")
        
        # xclip dene
        if shutil.which("xclip"):
            try:
                subprocess.run(["xclip", "-selection", "clipboard"], 
                             input=text.encode('utf-8'), timeout=2, check=True)
                print(f"[Agent] Panoya kopyalandı (xclip): '{text[:50]}'")
                return
            except Exception as e:
                print(f"[Agent] xclip başarısız: {e}")
        
        # xsel dene
        if shutil.which("xsel"):
            try:
                subprocess.run(["xsel", "--clipboard", "--input"], 
                             input=text.encode('utf-8'), timeout=2, check=True)
                print(f"[Agent] Panoya kopyalandı (xsel): '{text[:50]}'")
                return
            except Exception as e:
                print(f"[Agent] xsel başarısız: {e}")
        
        raise RuntimeError("Hiçbir pano aracı çalışmadı")
    
    def type_text(self, text):
        if not text:
            return
        self._ensure_pointer()
        print(f"[Agent] type_text: '{text}'")
        
        from evdev import ecodes
        
        # Modifier'ları temizle (Super/Meta HARİÇ — Activities'i kapatmasın)
        for key in [ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL, ecodes.KEY_LEFTSHIFT, 
                     ecodes.KEY_RIGHTSHIFT, ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT]:
            self._keyboard.write(ecodes.EV_KEY, key, 0)
        self._keyboard.syn()
        time.sleep(0.15)
        
        # YÖNTEM 1: wtype (Wayland native)
        try:
            result = subprocess.run(["wtype", text], capture_output=True, timeout=5)
            if result.returncode == 0:
                print(f"[Agent] type_text (wtype) OK: '{text}'")
                return
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[Agent] wtype başarısız: {e}")
        
        # YÖNTEM 2: Pano + Ctrl+V (click+text akışında çalışıyor!)
        try:
            self._set_clipboard(text)
            time.sleep(0.3)
            
            self._keyboard.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 1)
            self._keyboard.syn()
            time.sleep(0.08)
            self._keyboard.write(ecodes.EV_KEY, ecodes.KEY_V, 1)
            self._keyboard.syn()
            time.sleep(0.08)
            self._keyboard.write(ecodes.EV_KEY, ecodes.KEY_V, 0)
            self._keyboard.syn()
            time.sleep(0.05)
            self._keyboard.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 0)
            self._keyboard.syn()
            time.sleep(0.1)
            print(f"[Agent] type_text (pano+Ctrl+V) OK: '{text}'")
            # Debug log
            log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "agent_debug.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"TYPE_METHOD: pano+Ctrl+V kullanıldı: '{text}'\n")
        except Exception as e:
            print(f"[Agent] Pano başarısız ({e}), evdev raw deneniyor...")
            log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "agent_debug.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"TYPE_METHOD: pano BAŞARISIZ ({e}), evdev raw deneniyor\n")
            self.type_text_raw(text)

    def type_text_raw(self, text):
        """Karakter karakter yaz — önce xdotool dener, sonra evdev."""
        if not text:
            return
        
        # xdotool type dene (X11, Wayland'da çalışmayabilir)
        try:
            result = subprocess.run(
                ["xdotool", "type", "--clearmodifiers", "--delay", "50", text],
                capture_output=True, timeout=5,
                env={**os.environ, 'DISPLAY': ':0'}
            )
            if result.returncode == 0:
                print(f"[Agent] type_text_raw (xdotool): '{text}'")
                return
        except:
            pass
        
        self._ensure_pointer()
        from evdev import ecodes
        
        # Türkçe karakter → ASCII dönüşüm (GNOME arama için yeterli)
        char_map = {
            'a': (ecodes.KEY_A, False), 'b': (ecodes.KEY_B, False), 'c': (ecodes.KEY_C, False),
            'd': (ecodes.KEY_D, False), 'e': (ecodes.KEY_E, False), 'f': (ecodes.KEY_F, False),
            'g': (ecodes.KEY_G, False), 'h': (ecodes.KEY_H, False), 'i': (ecodes.KEY_I, False),
            'j': (ecodes.KEY_J, False), 'k': (ecodes.KEY_K, False), 'l': (ecodes.KEY_L, False),
            'm': (ecodes.KEY_M, False), 'n': (ecodes.KEY_N, False), 'o': (ecodes.KEY_O, False),
            'p': (ecodes.KEY_P, False), 'q': (ecodes.KEY_Q, False), 'r': (ecodes.KEY_R, False),
            's': (ecodes.KEY_S, False), 't': (ecodes.KEY_T, False), 'u': (ecodes.KEY_U, False),
            'v': (ecodes.KEY_V, False), 'w': (ecodes.KEY_W, False), 'x': (ecodes.KEY_X, False),
            'y': (ecodes.KEY_Y, False), 'z': (ecodes.KEY_Z, False),
            '0': (ecodes.KEY_0, False), '1': (ecodes.KEY_1, False), '2': (ecodes.KEY_2, False),
            '3': (ecodes.KEY_3, False), '4': (ecodes.KEY_4, False), '5': (ecodes.KEY_5, False),
            '6': (ecodes.KEY_6, False), '7': (ecodes.KEY_7, False), '8': (ecodes.KEY_8, False),
            '9': (ecodes.KEY_9, False),
            ' ': (ecodes.KEY_SPACE, False), '-': (ecodes.KEY_MINUS, False),
            '.': (ecodes.KEY_DOT, False), ',': (ecodes.KEY_COMMA, False),
            '/': (ecodes.KEY_SLASH, False),
            # Türkçe karakter destekleri (ASCII eşdeğerine çevirerek GNOME'da aramayı sağlar)
            'ı': (ecodes.KEY_I, False), 'i̇': (ecodes.KEY_I, False),
            'ş': (ecodes.KEY_S, False), 'ğ': (ecodes.KEY_G, False),
            'ü': (ecodes.KEY_U, False), 'ö': (ecodes.KEY_O, False),
            'ç': (ecodes.KEY_C, False),
        }
        
        print(f"[Agent] type_text_raw (evdev): '{text}'")
        for char in text.lower():
            if char in char_map:
                keycode, shift = char_map[char]
                if shift:
                    self._keyboard.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 1)
                    self._keyboard.syn()
                    time.sleep(0.03)
                
                self._keyboard.write(ecodes.EV_KEY, keycode, 1)
                self._keyboard.syn()
                time.sleep(0.05)
                self._keyboard.write(ecodes.EV_KEY, keycode, 0)
                self._keyboard.syn()
                
                if shift:
                    time.sleep(0.03)
                    self._keyboard.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, 0)
                    self._keyboard.syn()
                
                time.sleep(0.08)  # Tuşlar arası bekleme — GNOME'un yakalaması için
            else:
                # Bilinmeyen karakter, atla
                print(f"[Agent] Karakter atlandı: '{char}'")
        print(f"[Agent] type_text_raw tamamlandı")

    def press_key(self, key):
        if not key: return
        self._ensure_pointer()
        from evdev import ecodes
        keymap = {
            "enter": ecodes.KEY_ENTER, "return": ecodes.KEY_ENTER,
            "backspace": ecodes.KEY_BACKSPACE, "escape": ecodes.KEY_ESC, "esc": ecodes.KEY_ESC,
            "up": ecodes.KEY_UP, "down": ecodes.KEY_DOWN, "left": ecodes.KEY_LEFT, "right": ecodes.KEY_RIGHT,
            "space": ecodes.KEY_SPACE, "tab": ecodes.KEY_TAB
        }
        ev_key = keymap.get(key.lower())
        if ev_key:
            self._keyboard.write(ecodes.EV_KEY, ev_key, 1)
            self._keyboard.syn()
            time.sleep(0.08)
            self._keyboard.write(ecodes.EV_KEY, ev_key, 0)
            self._keyboard.syn()
            time.sleep(0.15)
            print(f"[Agent] ⌨️ press_key: {key} ({ev_key})")
        else:
            print(f"[Agent] ⚠️ press_key: '{key}' tanınmadı!")

    def hotkey(self, keys):
        """Tuş kombinasyonu gönder (örn: ['ctrl', 'c'], ['super'], ['alt', 'f4'])."""
        if not keys: return
        self._ensure_pointer()
        from evdev import ecodes
        
        keymap = {
            "ctrl": ecodes.KEY_LEFTCTRL, "control": ecodes.KEY_LEFTCTRL,
            "alt": ecodes.KEY_LEFTALT,
            "shift": ecodes.KEY_LEFTSHIFT,
            "super": ecodes.KEY_LEFTMETA, "meta": ecodes.KEY_LEFTMETA, "win": ecodes.KEY_LEFTMETA,
            "enter": ecodes.KEY_ENTER, "return": ecodes.KEY_ENTER,
            "tab": ecodes.KEY_TAB, "escape": ecodes.KEY_ESC, "esc": ecodes.KEY_ESC,
            "backspace": ecodes.KEY_BACKSPACE, "delete": ecodes.KEY_DELETE,
            "up": ecodes.KEY_UP, "down": ecodes.KEY_DOWN,
            "left": ecodes.KEY_LEFT, "right": ecodes.KEY_RIGHT,
            "space": ecodes.KEY_SPACE,
            "f1": ecodes.KEY_F1, "f2": ecodes.KEY_F2, "f3": ecodes.KEY_F3, "f4": ecodes.KEY_F4,
            "f5": ecodes.KEY_F5, "f11": ecodes.KEY_F11, "f12": ecodes.KEY_F12,
        }
        # Tek harfler: a-z
        for c in "abcdefghijklmnopqrstuvwxyz":
            keymap[c] = getattr(ecodes, f"KEY_{c.upper()}")
        
        ev_keys = []
        for k in keys:
            ev = keymap.get(k.lower())
            if ev:
                ev_keys.append(ev)
            else:
                print(f"[Agent] Bilinmeyen hotkey tuşu: {k}")
        
        if not ev_keys:
            return
        
        # Tüm tuşları bas
        for ev in ev_keys:
            self._keyboard.write(ecodes.EV_KEY, ev, 1)
            self._keyboard.syn()
            time.sleep(0.05)
        
        time.sleep(0.1)
        
        # Tüm tuşları bırak (ters sıra)
        for ev in reversed(ev_keys):
            self._keyboard.write(ecodes.EV_KEY, ev, 0)
            self._keyboard.syn()
            time.sleep(0.05)
        
        print(f"[Agent] ⌨️ Hotkey gönderildi: {keys}")

    def close(self):
        if getattr(self, '_pointer', None):
            try: self._pointer.close()
            except: pass
            self._pointer = None
        if getattr(self, '_scroll', None):
            try: self._scroll.close()
            except: pass
            self._scroll = None
        if getattr(self, '_keyboard', None):
            try: self._keyboard.close()
            except: pass
            self._keyboard = None


# ──────────────── Ana Ajan Sınıfı ────────────────

class ComputerAgent:
    """AI-powered computer control agent."""

    def __init__(self, vision_api):
        self.vision_api = vision_api
        self.state = AgentState.IDLE
        self.task = ""
        self.steps = []
        self.max_steps = 999999  # Sınırsız
        self.current_step = 0
        self.thread = None
        self.user_response = None
        self._user_response_event = threading.Event()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._input = None  # WaylandInputController
        self._last_screenshot_hash = None
        self._failed_clicks = []  # [(x, y), ...] başarısız tıklama koordinatları
        self._current_elements = {}
        
        try:
            from src.features.element_detector import ElementDetector
            self.element_detector = ElementDetector()
        except Exception as e:
            print(f"[Agent] ElementDetector yüklenemedi: {e}")
            self.element_detector = None

    def _get_screen_size(self):
        """Gerçek çözünürlüğü xdotool yerine AI'ın gördüğü ekran görüntüsünden al."""
        try:
            from PIL import Image
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            screenshot_path = os.path.join(project_root, "current_screen.png")
            if os.path.exists(screenshot_path):
                with Image.open(screenshot_path) as img:
                    return img.size[0], img.size[1]
        except Exception as e:
            print(f"[Agent] Ekran boyutu görselden okunamadı: {e}")
            
        # Fallback to xdotool
        try:
            result = subprocess.run(
                ["xdotool", "getdisplaygeometry"],
                capture_output=True, text=True, timeout=5,
                env={**os.environ, 'DISPLAY': ':0'}
            )
            parts = result.stdout.strip().split()
            return int(parts[0]), int(parts[1])
        except:
            return 1366, 768

    def _get_input(self):
        """Get or create input controller and update dimensions dynamically."""
        w, h = self._get_screen_size()
        if self._input is None:
            self._input = WaylandInputController(w, h)
        else:
            self._input.screen_w = w
            self._input.screen_h = h
        return self._input

    @property
    def status(self):
        with self._lock:
            last_step = self.steps[-1] if self.steps else None
            return {
                "state": self.state.value,
                "task": self.task,
                "current_step": self.current_step,
                "max_steps": self.max_steps,
                "last_action": last_step,
                "steps": self.steps[-10:],
            }

    def start(self, task):
        if self.state == AgentState.RUNNING:
            return {"error": "Ajan zaten çalışıyor."}
        self.task = task
        self.steps = []
        self.current_step = 0
        self.state = AgentState.RUNNING
        self._stop_event.clear()
        self._user_response_event.clear()
        self._last_screenshot_hash = None
        self._failed_clicks = []
        self.thread = threading.Thread(target=self._agent_loop, daemon=True)
        self.thread.start()
        return {"success": True, "message": "Ajan başlatıldı."}

    def stop(self):
        self._stop_event.set()
        self._user_response_event.set()
        self.state = AgentState.IDLE
        self._add_step("system", "Ajan kullanıcı tarafından durduruldu.", {})
        return {"success": True, "message": "Ajan durduruldu."}

    def respond(self, response):
        if self.state != AgentState.WAITING_USER:
            return {"error": "Ajan şu an kullanıcı yanıtı beklemiyor."}
        self.user_response = response
        self._user_response_event.set()
        return {"success": True}

    def _add_step(self, action, thought, params):
        step = {
            "step": self.current_step,
            "action": action,
            "thought": thought,
            "params": params,
            "timestamp": time.time(),
        }
        with self._lock:
            self.steps.append(step)
        print(f"[Agent] Adım {self.current_step}: {action} — {thought[:80]}")
        # Kullanıcının ajanın ne yapmaya çalıştığını görmesi için bildirim gönder
        #     import subprocess
        #     safe_thought = thought.replace('"', '').replace("'", "")
        #     subprocess.run(["notify-send", "-t", "3000", f"AI Aksiyonu: {action}", safe_thought], check=False)
        # except:
        #     pass

    def _check_task_done(self, task):
        """Ekrana bakarak görevin tamamlanıp tamamlanmadığını kontrol et."""
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            screenshot = os.path.join(project_root, "agent_screenshot.png")
            if not os.path.exists(screenshot):
                return False
            
            # Minimum 5 adım geçmeden kontrol yapma
            if self.current_step < 5:
                return False
            
            # Yapılan adımları özetle
            done_steps = []
            for s in self.steps[-5:]:
                if s['action'] in ('click', 'typed', 'type_text'):
                    detail = s.get('thought', '')
                    if 'text' in s.get('params', {}):
                        detail += f" (yazıldı: {s['params']['text']})"
                    done_steps.append(f"- {s['action']}: {detail}")
            steps_summary = "\n".join(done_steps) if done_steps else "Henüz adım yok"
            
            # İndirme görevi için özel kontrol
            task_lower = task.lower()
            is_download_task = any(kw in task_lower for kw in ["indir", "yükle", "kur", "install", "download"])
            
            if is_download_task:
                check_prompt = f"""GÖREV: {task}

YAPILAN ADIMLAR:
{steps_summary}

Ekrana DİKKATLİCE bak. Aşağıdaki SOMUT kanıtlardan en az birini görüyor musun?
1. İndirme progress barı veya yüzde göstergesi
2. "İndiriliyor..." veya "Downloading..." yazısı
3. Dosya boyutu bilgisi (MB/GB)
4. İndirme diyalogu (kaydet penceresi)
5. "Yükleniyor" spinner'ı

SADECE bu somut kanıtlardan birini GERÇEKTEN görüyorsan EVET yaz.
Sadece bir butona tıklanmış olması YETERLİ DEĞİL.
Emin değilsen HAYIR yaz."""
            else:
                check_prompt = f"""GÖREV: {task}

YAPILAN ADIMLAR:
{steps_summary}

Ekrana bak. Bu görev tamamlandı mı?
Sadece EVET veya HAYIR yaz."""

            response = self.vision_api.generate_vision_response(check_prompt, screenshot)
            answer = response.strip().upper().replace('"', '').replace("'", "")
            print(f"[Agent] Done check: '{answer}'")
            return "EVET" in answer or "YES" in answer
        except Exception as e:
            print(f"[Agent] Done check hatası: {e}")
            return False

    def _take_screenshot(self):
        os.environ.setdefault('DISPLAY', ':0')
        from src.features.screen_capture import ScreenCapture
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        path = os.path.join(project_root, "agent_screenshot.png")
        capturer = ScreenCapture()
        result = capturer.capture_full_screen(path)
        if result:
            grid_path = os.path.join(project_root, "agent_screenshot_grid.png")
            if self.element_detector:
                self._current_elements = self.element_detector.detect_and_draw(result, grid_path)
            else:
                self._current_elements = {}
                import shutil
                shutil.copy2(result, grid_path)
            return result
        return result

    def _ask_vision_ai(self, screenshot_path, task, history):
        w, h = self._get_screen_size()
        screen_info = f"""\nEKRAN: {w}x{h} piksel.
Öğelerin etrafında YEŞİL KUTULAR ve SARI NUMARALAR [1], [2], [3] var. Tıklamak için element_id kullan.
Yazı yazmak gerekiyorsa click aksiyonuna "text" alanı ekle."""

        # Son 4 adımı göster
        history_text = ""
        if history and len(history) > 0:
            recent = history[-4:]
            lines = []
            for s in recent:
                detail = ""
                if 'text' in s.get('params', {}):
                    detail = f' → yazıldı: "{s["params"]["text"]}"'
                elif 'x' in s.get('params', {}) and 'y' in s.get('params', {}):
                    detail = f" @ ({s['params']['x']},{s['params']['y']})"
                lines.append(f"Adım {s['step']}: {s['action']}{detail}")
            history_text = "\nYAPILAN ADIMLAR:\n" + "\n".join(lines)

        prompt = f"""GÖREV: {task}
{screen_info}
{history_text}

Ekranı dikkatlice incele. Eğer görev ZATEN TAMAMLANDIYSA hemen done dön!
Görev henüz tamamlanmadıysa, sonraki TEK aksiyonu JSON olarak dön."""

        # İşaretli screenshot'u kullan (varsa)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        grid_path = os.path.join(project_root, "agent_screenshot_grid.png")
        vision_path = grid_path if os.path.exists(grid_path) else screenshot_path

        try:
            full_prompt = AGENT_SYSTEM_PROMPT + "\n\n" + prompt
            return self.vision_api.generate_vision_response(full_prompt, vision_path)
        except Exception as e:
            return json.dumps({"action": "done", "summary": f"Hata: {str(e)}", "thought": "API hatası"})

    def _parse_action(self, response):
        response = response.strip()
        # Direct JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        # JSON in text
        m = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        # Code block
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
                
        # Agresif Regex Kurtarma (Bozuk JSON için, örn: "x": 228, 958])
        print("[Agent] Bozuk JSON tespit edildi, regex ile kurtarılıyor...")
        action_match = re.search(r'"action"\s*:\s*"([^"]+)"', response)
        action = action_match.group(1) if action_match else "done"
        
        x_match = re.search(r'"x"\s*:\s*(\d+)', response)
        y_match = re.search(r'"y"\s*:\s*(\d+)', response)
        id_match = re.search(r'"element_id"\s*:\s*(\d+)', response)
        
        x_val = int(x_match.group(1)) if x_match else None
        y_val = int(y_match.group(1)) if y_match else None
        id_val = int(id_match.group(1)) if id_match else None
        
        # Eğer y bulunamadıysa ama x'ten sonra virgül ve sayı varsa (ör: "x": 228, 958])
        if x_val is not None and y_val is None:
            xy_match = re.search(r'"x"\s*:\s*\[?(\d+)[,\s]+(\d+)', response)
            if xy_match:
                x_val = int(xy_match.group(1))
                y_val = int(xy_match.group(2))
                
        # text, key, vs. için
        text_match = re.search(r'"text"\s*:\s*"([^"]+)"', response)
        key_match = re.search(r'"key"\s*:\s*"([^"]+)"', response)
        thought_match = re.search(r'"thought"\s*:\s*"([^"]+)"', response)
        
        if action in ["click", "double_click", "move_to", "scroll", "right_click"]:
            ret = {"action": action, "thought": thought_match.group(1) if thought_match else "Regex kurtarma başarılı."}
            if id_val is not None:
                ret["element_id"] = id_val
            if x_val is not None: ret["x"] = x_val
            if y_val is not None: ret["y"] = y_val
            return ret
        elif action in ["type_text", "type", "press_key", "press", "hotkey"]:
            ret = {
                "action": action,
                "text": text_match.group(1) if text_match else "",
                "key": key_match.group(1) if key_match else "",
                "thought": thought_match.group(1) if thought_match else "Regex kurtarma başarılı."
            }
            if id_val is not None:
                ret["element_id"] = id_val
            return ret
            
        return {"action": "done", "summary": "AI yanıtı işlenemedi: " + response[:100], "thought": "Parse hatası"}

    def _normalize_action(self, data):
        """Parse edilmiş action verisini normalize et."""
        # element_id liste olarak geldiyse int'e çevir
        if "element_id" in data:
            eid = data["element_id"]
            if isinstance(eid, (list, tuple)):
                eid = eid[0] if eid else 0
            try:
                data["element_id"] = int(eid)
            except (ValueError, TypeError):
                data["element_id"] = 0
        return data

    def _extract_text_from_task(self, task):
        """Görev metninden yazılacak arama/URL metnini çıkar."""
        task_lower = task.lower().strip()
        
        # "X ara" kalıbı (Türkçe)
        patterns = [
            r'(?:google\'?da|chromeda|internette|tarayıcıda)\s+(.+?)(?:\s+ara|\s+arat|\s+bul|$)',
            r'ara\s+(.+?)(?:\s+sitesini|\s+sayfasını|$)',
            r'(.+?)\s+(?:ara\b|arat\b|bul\b)',
            r'(?:yaz|yazı yaz|metin gir)\s*[:\s]+(.+)',
            r'(?:git|gir|aç)\s+(.+?)(?:\s+sitesine|\s+sayfasına|\s+adresine|$)',
            r'(?:search for|search|type|write)\s+(.+)',
        ]
        
        for pattern in patterns:
            m = re.search(pattern, task_lower)
            if m:
                text = m.group(1).strip()
                # Çok kısa veya çok uzun metinleri filtrele
                if 1 < len(text) < 200:
                    # Orijinal görevden (büyük/küçük harf korunaklı) aynı kısmı çıkar
                    idx = task_lower.find(text)
                    if idx >= 0:
                        return task[idx:idx+len(text)].strip()
                    return text
        
        # Kalıp bulunamazsa, görevin son kısmını al (genellikle aranacak kısım sonda olur)
        # "chrome aç umut karaçelebi ara" → "umut karaçelebi"  
        words = task.split()
        # "ara", "arat", "bul" kelimesini bul ve ondan önceki kısımları al
        for keyword in ["ara", "arat", "bul"]:
            if keyword in [w.lower().rstrip('.,!?') for w in words]:
                idx = next(i for i, w in enumerate(words) if w.lower().rstrip('.,!?') == keyword)
                # keyword'den önceki kelimelerden uygulama adlarını çıkar
                before = words[:idx]
                # "chrome aç" gibi komutları atla
                skip_words = {"chrome", "aç", "açık", "firefox", "tarayıcı", "google", "açıp"}
                search_words = [w for w in before if w.lower() not in skip_words]
                if search_words:
                    return " ".join(search_words)
        
        return None

    def _adjust_for_repeated_click(self, x, y):
        """Kapatıldı: Eski sistemde aynı yere tıklanırsa koordinat kaydırılıyordu, bu hassasiyeti bozduğu için iptal edildi."""
        return x, y

    def _refine_click_coords(self, x, y, thought=""):
        """Yakınlaştırma ile tıklama koordinatını düzelt (2-pass zoom-refine)."""
        try:
            from PIL import Image, ImageDraw

            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            screen_path = os.path.join(project_root, "agent_screenshot.png")
            if not os.path.exists(screen_path):
                return x, y

            img = Image.open(screen_path)
            sw, sh = img.size

            # 300x300 bölge kırp (hedef merkezde)
            crop_size = 300
            half = crop_size // 2
            cx1 = max(0, x - half)
            cy1 = max(0, y - half)
            cx2 = min(sw, x + half)
            cy2 = min(sh, y + half)

            cropped = img.crop((cx1, cy1, cx2, cy2))
            cw, ch = cropped.size

            # Kırpılmış görüntüye ince grid ekle (50px aralık)
            draw = ImageDraw.Draw(cropped, 'RGBA')
            for gx in range(0, cw, 50):
                draw.line([(gx, 0), (gx, ch)], fill=(0, 200, 0, 80), width=1)
                draw.text((gx + 2, 2), str(cx1 + gx), fill=(0, 200, 0, 180))
            for gy in range(0, ch, 50):
                draw.line([(0, gy), (cw, gy)], fill=(0, 200, 0, 80), width=1)
                draw.text((2, gy + 2), str(cy1 + gy), fill=(0, 200, 0, 180))

            # Hedef noktayı işaretle
            lx, ly = x - cx1, y - cy1
            draw.ellipse([(lx-5, ly-5), (lx+5, ly+5)], outline="yellow", width=2)

            zoom_path = os.path.join(project_root, "agent_zoom.png")
            cropped.save(zoom_path)

            # AI'a yakınlaştırılmış görüntüyü gönder
            refine_prompt = f"""Bu yakınlaştırılmış ekran görüntüsünde sarı daire ile işaretlenmiş yere tıklamak istiyorum.
Hedef: {thought}
Görüntü sol üst köşesi ekranın ({cx1},{cy1}) noktasıdır.
Yeşil çizgiler koordinat gridini gösterir.

Sarı dairenin gerçekten hedefin merkezinde olup olmadığını kontrol et.
Eğer hedefin merkezindeyse aynı koordinatı, değilse DOĞRU koordinatı dön.

SADECE JSON dön: {{"x": EKRAN_X, "y": EKRAN_Y}}"""

            response = self.vision_api.generate_vision_response(refine_prompt, zoom_path)
            print(f"[Refine] Zoom yanıtı: {response[:100]}")

            # JSON'dan koordinatları çıkar
            m = re.search(r'\{\s*"x"\s*:\s*(\d+)\s*,\s*"y"\s*:\s*(\d+)\s*\}', response)
            if m:
                new_x, new_y = int(m.group(1)), int(m.group(2))
                # Mantıklı aralıkta mı?
                if 0 <= new_x < sw and 0 <= new_y < sh:
                    if new_x != x or new_y != y:
                        print(f"[Refine] 🎯 Koordinat düzeltildi: ({x},{y}) → ({new_x},{new_y})")
                    return new_x, new_y

        except Exception as e:
            print(f"[Refine] Zoom hatası (orijinal koordinat kullanılacak): {e}")

        return x, y

    def _save_click_debug(self, x, y, thought=""):
        """Tıklama hedefini ekran görüntüsü üzerine çizip kaydet."""
        try:
            from PIL import Image, ImageDraw
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            screen_path = os.path.join(project_root, "agent_screenshot.png")
            if not os.path.exists(screen_path):
                return

            img = Image.open(screen_path).copy()
            draw = ImageDraw.Draw(img, 'RGBA')
            r = 18

            # Kırmızı daire
            draw.ellipse([(x-r, y-r), (x+r, y+r)], fill=(255, 0, 0, 120), outline="red", width=2)
            # Çapraz çizgiler
            draw.line([(x-25, y), (x+25, y)], fill="red", width=2)
            draw.line([(x, y-25), (x, y+25)], fill="red", width=2)
            # Koordinat etiketi
            label = f"({x},{y})"
            draw.rectangle([(x+20, y-18), (x+20+len(label)*7, y-4)], fill=(0,0,0,180))
            draw.text((x+22, y-17), label, fill="white")

            log_dir = os.path.join(project_root, "logs", "clicks")
            os.makedirs(log_dir, exist_ok=True)
            debug_path = os.path.join(log_dir, f"click_{self.current_step}_{int(time.time())}.png")
            img.save(debug_path)
            print(f"[Debug] 🎯 Tıklama hedefi kaydedildi: {debug_path}")
        except Exception as e:
            print(f"[Debug] Click görsel hatası: {e}")

    def _execute_action(self, action_data):
        """Execute action using Wayland-compatible input."""
        action = action_data.get("action", "")
        thought = action_data.get("thought", "")
        params = {k: v for k, v in action_data.items() if k not in ("action", "thought")}
        self._add_step(action, thought, params)

        def _safe_int(val, default=0):
            """Safely convert a value to int, handling lists, dicts, etc."""
            if isinstance(val, (list, tuple)):
                val = val[0] if val else default
            if isinstance(val, dict):
                val = next(iter(val.values()), default)
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return default

        inp = self._get_input()

        # Tıklama dışı aksiyonlarda başarısız listesini temizle
        if action not in ("click", "double_click", "right_click", "move_to"):
            self._failed_clicks = []
            
        def _get_coords(action_data):
            # Element ID varsa sözlükten (X,Y) çek
            if "element_id" in action_data:
                eid = _safe_int(action_data["element_id"])
                if eid in self._current_elements:
                    return self._current_elements[eid]["x"], self._current_elements[eid]["y"]
                else:
                    print(f"[Agent] HATA: {eid} numaralı element bulunamadı! Tıklama iptal.")
                    return None  # Element yok → tıklama iptal
            return _safe_int(action_data.get("x", 0)), _safe_int(action_data.get("y", 0))

        try:
            if action == "click":
                coords = _get_coords(action_data)
                if coords is None:
                    print(f"[Agent] ⚠️ Geçersiz element, adım atlanıyor.")
                    return True  # Devam et ama tıklama
                x, y = coords
                self._save_click_debug(x, y, thought)
                inp.click(x, y)
                self._failed_clicks.append((x, y))
                
                # AI click aksiyonuna "text" alanı eklediyse → tıkla + yaz
                text = action_data.get("text", "")
                if text and not self._stop_event.is_set():
                    print(f"[Agent] 🔤 Click+Text algılandı: '{text}'")
                    time.sleep(1.0)  # Odaklanma için bekle
                    # Önce mevcut metni temizle: Ctrl+A (hepsini seç) + Delete
                    inp.hotkey(["ctrl", "a"])
                    time.sleep(0.15)
                    inp.press_key("delete")
                    time.sleep(0.2)
                    # Şimdi yaz
                    inp.type_text(text)
                    self._add_step("typed", f"Yazıldı: {text}", {"text": text})
                    
                    # Arama kutusuna yazıldıysa otomatik Enter bas
                    # Sadece ekranın orta bölgesindeki geniş arama kutularında
                    # (Activities hariç, form/editör alanlarını kapsamaz)
                    element_id_val = action_data.get("element_id", 0)
                    is_center_search = (300 < y < 500) and (400 < x < 900)  # Ekran ortası
                    is_activities = element_id_val == 1 and y < 50
                    if is_center_search and not is_activities:
                        time.sleep(0.3)
                        inp.press_key("enter")
                        print(f"[Agent] ⏎ Otomatik Enter basıldı (arama kutusu @ {x},{y})")
                    
                    # Debug: yazma sonucunu logla
                    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "agent_debug.log")
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"TYPE_TEXT: '{text}' yazıldı (click+text akışı)\n")

            elif action == "double_click":
                coords = _get_coords(action_data)
                if coords is None:
                    return True
                x, y = coords
                self._save_click_debug(x, y, thought)
                inp.double_click(x, y)
                self._failed_clicks.append((x, y))

            elif action == "right_click":
                coords = _get_coords(action_data)
                if coords is None:
                    return True
                x, y = coords
                inp.click(x, y, button="right")

            elif action == "type_text":
                # Geriye uyumluluk: AI type_text gönderirse de çalışsın
                if "element_id" in action_data:
                    x, y = _get_coords(action_data)
                    if x != 0 and y != 0:
                        inp.click(x, y)
                        time.sleep(0.5)
                inp.type_text(action_data.get("text", ""))

            elif action == "hotkey":
                keys = action_data.get("keys", [])
                if keys:
                    inp.hotkey(keys)

            elif action in ("press_key", "press"):
                key = action_data.get("key", "")
                if key:
                    inp.press_key(key)

            elif action in ("type_text", "type") and "element_id" not in action_data:
                # Sadece type/type_text aksiyonu (element_id yoksa)
                inp.type_text(action_data.get("text", ""))

            elif action == "scroll":
                inp.scroll(action_data.get("direction", "down"), _safe_int(action_data.get("amount", 3), 3))

            elif action == "move_to":
                x, y = _get_coords(action_data)
                inp.move_to(x, y)

            elif action == "wait":
                time.sleep(min(float(action_data.get("seconds", 1)), 10))

            elif action == "ask_user":
                self.state = AgentState.WAITING_USER
                self._user_response_event.clear()
                self._user_response_event.wait(timeout=300)
                if self._stop_event.is_set():
                    return False
                if self.user_response:
                    self._add_step("user_responded", "Kullanıcı yanıtı alındı", {})
                    inp.type_text(self.user_response)
                    self.user_response = None
                self.state = AgentState.RUNNING

            elif action == "done":
                summary = action_data.get("summary", "Görev tamamlandı.")
                self._add_step("done", summary, {})
                self.state = AgentState.DONE
                return False

            else:
                self._add_step("unknown", f"Bilinmeyen aksiyon: {action}", {})

            return True

        except Exception as e:
            self._add_step("error", f"Aksiyon hatası: {str(e)[:80]}", {})
            return True



    def _agent_loop(self):
        try:
            time.sleep(2)
            error_count = 0
            recent_element_ids = []  # Döngü algılama için son tıklanan element_id'ler
            
            while self.current_step < self.max_steps:
                if self._stop_event.is_set():
                    break
                self.current_step += 1

                screenshot_path = self._take_screenshot()
                if not screenshot_path:
                    self._add_step("error", "Ekran görüntüsü alınamadı", {})
                    time.sleep(2)
                    error_count += 1
                    if error_count > 3: break
                    continue

                response = self._ask_vision_ai(screenshot_path, self.task, self.steps)
                if self._stop_event.is_set():
                    break

                # Boş yanıt kontrolü — retry
                if not response or not response.strip():
                    print("[Agent] ⚠️ AI boş yanıt döndü, tekrar deneniyor...")
                    error_count += 1
                    time.sleep(2)
                    if error_count > 3: break
                    continue

                # 🔍 TEŞHIS: Dosyaya logla
                log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "agent_debug.log")
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"ADIM {self.current_step} — {time.strftime('%H:%M:%S')}\n")
                    f.write(f"GÖREV: {self.task}\n")
                    f.write(f"AI YANITI:\n{response[:1000]}\n")

                action_data = self._parse_action(response)
                action_data = self._normalize_action(action_data)
                
                # Parse hatası kontrolü — retry
                if action_data.get("action") == "done" and "işlenemedi" in action_data.get("summary", ""):
                    print(f"[Agent] ⚠️ Parse hatası, tekrar deneniyor...")
                    error_count += 1
                    time.sleep(2)
                    if error_count > 3: break
                    continue
                
                # 🔍 TEŞHIS: Element bilgisi dosyaya
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"PARSED: {json.dumps(action_data, ensure_ascii=False, default=str)}\n")
                    if "element_id" in action_data:
                        eid = action_data["element_id"]
                        if isinstance(eid, (list, tuple)): eid = eid[0] if eid else 0
                        try: eid = int(eid)
                        except: eid = 0
                        if eid in self._current_elements:
                            coords = self._current_elements[eid]
                            f.write(f"ELEMENT {eid} → ({coords['x']}, {coords['y']})\n")
                        else:
                            f.write(f"ELEMENT {eid} BULUNAMADI! Mevcut: {list(self._current_elements.keys())[:15]}\n")
                    f.write(f"TOPLAM ELEMENT: {len(self._current_elements)}\n")
                    f.write(f"{'='*60}\n")
                
                # Eğer ardışık hatalar oluyorsa (sonsuz döngüyü önle)
                if action_data.get("action") in ["unknown", "error", "done"]:
                    error_count += 1
                else:
                    error_count = 0
                    
                if error_count > 4:
                    self._add_step("error", "Üst üste çok fazla hata alındı, ajan durduruluyor.", {})
                    break

                # Döngü algılama: Aynı element_id tekrar tıklanıyorsa
                if action_data.get("action") == "click" and "element_id" in action_data:
                    eid = action_data["element_id"]
                    if isinstance(eid, (list, tuple)): eid = eid[0] if eid else 0
                    try: eid = int(eid)
                    except: eid = 0
                    recent_element_ids.append(eid)
                    if len(recent_element_ids) > 8:
                        recent_element_ids.pop(0)
                    repeat_count = recent_element_ids.count(eid)
                    if repeat_count >= 5:
                        # 5+ tekrar → tamamen dur
                        self._add_step("done", "Aynı öğeye çok fazla tıklandı, görev sonlandırıldı.", {})
                        print("[Agent] ⚠️ Döngü algılandı: 5+ tekrar. Durduruluyor.")
                        break
                    elif repeat_count >= 3:
                        # 3 tekrar → scroll yap, belki farklı elementler görünür
                        print("[Agent] ⚠️ Aynı elemente 3 kez tıklandı, scroll deneniyor...")
                        inp = self._get_input()
                        inp.scroll("down", 3)
                        recent_element_ids.clear()
                        time.sleep(1)
                        continue

                if not self._execute_action(action_data):
                    break

                # Her aksiyondan sonra görev tamamlanma kontrolü (3. adımdan itibaren)
                if self.current_step >= 3 and not self._stop_event.is_set():
                    if self._check_task_done(self.task):
                        self._add_step("done", "Görev tamamlandı.", {})
                        self.state = AgentState.DONE
                        print("[Agent] ✅ Görev tamamlandı algılandı.")
                        break

                # Akıllı bekleme: aksiyona göre farklı süre bekle
                action_type = action_data.get("action", "")
                thought_text = action_data.get("thought", "").lower()
                
                if action_type == "click" and any(kw in thought_text for kw in 
                    ["açıyorum", "açacağım", "açılacak", "açmak", "tıklıyorum", "launch"]):
                    # Uygulama açma veya sayfa navigasyonu — uzun bekle
                    wait_time = 3.0
                elif action_type == "click" and any(kw in thought_text for kw in 
                    ["bağlantı", "link", "sayfa", "site", "indir", "download"]):
                    # Link tıklama — orta bekle
                    wait_time = 2.5
                elif action_type == "hotkey":
                    wait_time = 2.0
                else:
                    wait_time = 1.5
                
                time.sleep(wait_time)

            if self.state == AgentState.RUNNING:
                self.state = AgentState.DONE
                self._add_step("done", f"Maksimum adım sayısına ({self.max_steps}) ulaşıldı.", {})

        except Exception as e:
            self.state = AgentState.ERROR
            self._add_step("error", f"Ajan hatası: {str(e)}", {})
            print(f"[Agent] Fatal error: {e}")
        finally:
            if self._input:
                self._input.close()
                self._input = None
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            path = os.path.join(project_root, "agent_screenshot.png")
            if os.path.exists(path):
                os.remove(path)
