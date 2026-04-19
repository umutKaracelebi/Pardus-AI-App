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


AGENT_SYSTEM_PROMPT = """Sen bir bilgisayar kontrol ajanısın. Kullanıcının verdiği görevi tamamlamak için bilgisayarı kontrol edeceksin.

Her adımda sana ekranın görüntüsü gönderilecek. Sen ekranı analiz edip yapılması gereken bir SONRAKİ aksiyonu JSON formatında döneceksin.

SADECE aşağıdaki aksiyonlardan birini kullan:

1. Tıklama: {"action": "click", "element_id": 12, "thought": "..."}
2. Çift tıklama: {"action": "double_click", "element_id": 12, "thought": "..."}
3. Sağ tıklama: {"action": "right_click", "element_id": 12, "thought": "..."}
4. Yazma: {"action": "type_text", "element_id": 12, "text": "yazılacak metin", "thought": "..."}
5. Kısayol tuşu: {"action": "hotkey", "keys": ["ctrl", "c"], "thought": "..."}
6. Tek tuş basma: {"action": "press_key", "key": "enter", "thought": "..."}
7. Kaydırma: {"action": "scroll", "direction": "down", "amount": 3, "thought": "..."}
8. Mouse taşıma: {"action": "move_to", "element_id": 12, "thought": "..."}
9. Bekleme: {"action": "wait", "seconds": 2, "thought": "..."}
10. Görev tamamlandı: {"action": "done", "summary": "Ne yapıldığının özeti", "thought": "..."}

KOORDİNAT & TIKLAMA KURALLARI:
- DİKKAT: Kendi içsel piksel tahminini, normalize (0-1000) veya bounding box koordinat sistemini KESİNLİKLE KULLANMA! x ve y DEĞERİ DÖNME.
- Resmin üzerinde yeşil kutularla çevrelenmiş nesneler ve siyah arka planlı SARI RENKLİ NUMARALAR [1], [2], [3] var.
- Tıklamak istediğin öğenin üzerindeki Numarayı (ID) bul ve bunu "element_id" olarak gönder.
- Yazı yazmak istediğinde de "element_id" parametresini mutlaka gönder! Böylece ajan önce arama kutusuna tıklar, sonra yazıyı yazar.
- Örnek: Eğer hedefin yanındaki sarı yazıda [45] yazıyorsa, {"action": "click", "element_id": 45} dönmelisin.

GENEL KURALLAR:
- Her yanıtta SADECE TEK BİR JSON nesnesi dön, başka hiçbir şey yazma.
- "thought" alanında ne gördüğünü ve neden bu aksiyonu seçtiğini kısaca açıkla.
- KULLANICIYA SORU SORMA. Ekranı kendin analiz et ve kendi kararını ver. Otonom çalış.
- Görev tamamlandığında MUTLAKA "done" aksiyonu dön.
- Menüler açıldıktan sonra yüklenmesi için kısa "wait" kullan.
- Emin olmadığın durumlarda bile en mantıklı aksiyonu kendin seç ve uygula.
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
                    ecodes.KEY_V, ecodes.KEY_C, ecodes.KEY_X, ecodes.KEY_ENTER, ecodes.KEY_BACKSPACE, ecodes.KEY_ESC,
                    ecodes.KEY_UP, ecodes.KEY_DOWN, ecodes.KEY_LEFT, ecodes.KEY_RIGHT, ecodes.KEY_SPACE, ecodes.KEY_TAB,
                    ecodes.KEY_Q, ecodes.KEY_W, ecodes.KEY_E, ecodes.KEY_R, ecodes.KEY_T, ecodes.KEY_Y, ecodes.KEY_U,
                    ecodes.KEY_I, ecodes.KEY_O, ecodes.KEY_P, ecodes.KEY_A, ecodes.KEY_S, ecodes.KEY_D, ecodes.KEY_F,
                    ecodes.KEY_G, ecodes.KEY_H, ecodes.KEY_J, ecodes.KEY_K, ecodes.KEY_L, ecodes.KEY_Z, ecodes.KEY_X,
                    ecodes.KEY_C, ecodes.KEY_V, ecodes.KEY_B, ecodes.KEY_N, ecodes.KEY_M,
                    ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4, ecodes.KEY_5,
                    ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8, ecodes.KEY_9, ecodes.KEY_0
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
        time.sleep(0.12)
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
        if shutil.which("wl-copy"):
            subprocess.run(["wl-copy"], input=text.encode('utf-8'))
        elif shutil.which("xclip"):
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode('utf-8'))
        elif shutil.which("xsel"):
            subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode('utf-8'))
        else:
            print("[Agent] wl-copy bulunamadı, xdotool ile clipboard deneniyor...")
            subprocess.run(["xdotool", "type", "--delay", "10", text], env=self._env, check=False)
    
    def type_text(self, text):
        if not text:
            return
        self._ensure_pointer()
        
        # 1. Native Wayland aracı (wtype) kuruluysa onu kullan (EN GÜVENLİ)
        import shutil, subprocess
        if shutil.which("wtype"):
            try:
                subprocess.run(["wtype", text], check=True)
                print(f"[Agent] wtype ile yazıldı: {text}")
                return
            except Exception as e:
                print(f"[Agent] wtype hatası: {e}")
                
        # 2. wtype yoksa Pano + Ctrl-V taktiği (YEDEK)
        self._set_clipboard(text)
        time.sleep(0.2)  # Panonun senkronize olmasını bekle
        
        from evdev import ecodes
        # Ctrl bas
        self._keyboard.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 1)
        self._keyboard.syn()
        time.sleep(0.05) # GNOME'un algılaması için biraz bekle
        # V bas
        self._keyboard.write(ecodes.EV_KEY, ecodes.KEY_V, 1)
        self._keyboard.syn()
        time.sleep(0.05)
        # V bırak
        self._keyboard.write(ecodes.EV_KEY, ecodes.KEY_V, 0)
        self._keyboard.syn()
        time.sleep(0.02)
        # Ctrl bırak
        self._keyboard.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 0)
        self._keyboard.syn()
        time.sleep(0.05)

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
            time.sleep(0.02)
            self._keyboard.write(ecodes.EV_KEY, ev_key, 0)
            self._keyboard.syn()
            time.sleep(0.05)

    def hotkey(self, keys):
        if not keys: return
        # Şimdilik sadece metin yazma ve enter/backspace yetiyor.
        pass

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
        self.max_steps = 50
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
        try:
            import subprocess
            safe_thought = thought.replace('"', '').replace("'", "")
            subprocess.run(["notify-send", "-t", "3000", f"AI Aksiyonu: {action}", safe_thought], check=False)
        except:
            pass

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
DİKKAT: Ekrandaki tıklanabilir nesnelerin etrafı yeşil kutularla çevrilmiş ve yanlarına [1], [2] gibi sarı numaralar eklenmiştir.

NASIL AKSİYON ALINIR:
1. Gözünle ekrana bak, hedefini bul.
2. Hedefin üzerindeki SARI KUTU NUMARASINI oku.
3. "click", "type_text", "double_click" veya "right_click" yapacaksan x ve y parametreleri yerine sadece "element_id" dön!
4. Örnek: Hedef [12] numarada ise → {{"action": "type_text", "element_id": 12, "text": "Pardus"}}
ASLA PİKSEL TAHMİNİ YAPMA (x, y kullanma)! Sadece numaraları kullan."""

        # Son 2 adımı göster (daha fazlası AI'ı karıştırıyor)
        history_text = ""
        if history and len(history) > 0:
            recent = history[-2:]
            lines = []
            for s in recent:
                coords = ""
                if 'x' in s.get('params', {}) and 'y' in s.get('params', {}):
                    coords = f" @ ({s['params']['x']},{s['params']['y']})"
                lines.append(f"Adım {s['step']}: {s['action']}{coords}")
            history_text = "\nSon adımlar: " + " → ".join(lines)

        prompt = f"""GÖREV: {task}
{screen_info}
{history_text}

Ekranı dikkatlice incele. Görevi tamamlamak için sonraki TEK aksiyonu JSON olarak dön.
Her tıklamada hedefin TAM MERKEZİNİ bul. Kenara veya köşeye değil, ortasına tıkla."""

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
                    print(f"[Agent] HATA: {eid} numaralı element bulunamadı! Eski değerlere düşülüyor.")
            return _safe_int(action_data.get("x", 0)), _safe_int(action_data.get("y", 0))

        try:
            if action == "click":
                x, y = _get_coords(action_data)
                self._save_click_debug(x, y, thought)
                inp.click(x, y)
                self._failed_clicks.append((x, y))

            elif action == "double_click":
                x, y = _get_coords(action_data)
                self._save_click_debug(x, y, thought)
                inp.double_click(x, y)
                self._failed_clicks.append((x, y))

            elif action == "right_click":
                x, y = _get_coords(action_data)
                inp.click(x, y, button="right")

            elif action == "type_text":
                # Eğer element_id verildiyse, yazmadan önce o kutuya tıkla ve odaklan
                if "element_id" in action_data:
                    x, y = _get_coords(action_data)
                    if x != 0 and y != 0:
                        inp.click(x, y)
                        time.sleep(0.5) # İmlecin yanıp sönmeye başlamasını bekle
                inp.type_text(action_data.get("text", ""))

            elif action == "hotkey":
                keys = action_data.get("keys", [])
                if keys:
                    inp.hotkey(keys)

            elif action == "press_key":
                key = action_data.get("key", "")
                if key:
                    inp.press_key(key)

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
            time.sleep(1)
            error_count = 0
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

                action_data = self._parse_action(response)
                
                # Eğer ardışık hatalar oluyorsa (sonsuz döngüyü önle)
                if action_data.get("action") in ["unknown", "error", "done"]:
                    error_count += 1
                else:
                    error_count = 0
                    
                if error_count > 4:
                    self._add_step("error", "Üst üste çok fazla hata alındı, ajan durduruluyor.", {})
                    break

                if not self._execute_action(action_data):
                    break

                time.sleep(1)

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
