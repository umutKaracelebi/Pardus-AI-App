"""
Browser Agent — Playwright tabanlı otonom tarayıcı ajan.
DOM çıkarır → Qwen'e gönderir → Gelen aksiyonu çalıştırır → Döngü.

Hem Firefox hem Chromium destekler.
"""
import os
import json
import time
import asyncio
import threading
import re
import base64
from enum import Enum


class BrowserAgentState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


BROWSER_AGENT_SYSTEM_PROMPT = """Sen bir tarayıcı otomasyon ajanısın. Kullanıcının verdiği görevi tamamlamak için web sayfalarını kontrol edeceksin.

Her adımda sana sayfanın DOM yapısı (interaktif elementler listesi) verilecek.
Yapılması gereken SONRAKİ aksiyonu JSON formatında dön.

AKSİYONLAR:
1. Tıklama: {"action": "click", "element_id": 5, "thought": "..."}
2. Metin yazma: {"action": "type", "element_id": 5, "text": "yazılacak metin", "thought": "..."}
3. Sayfaya git: {"action": "navigate", "url": "https://...", "thought": "..."}
4. Kaydırma: {"action": "scroll", "direction": "down", "amount": 500, "thought": "..."}
5. Bekle: {"action": "wait", "seconds": 2, "thought": "..."}
6. Enter tuşu: {"action": "press_key", "key": "Enter", "thought": "..."}
7. Metin çıkar: {"action": "extract", "thought": "..."}
8. Görev tamamlandı: {"action": "done", "summary": "Sonuç özeti", "thought": "..."}

ELEMENT LİSTESİ FORMATI:
Her satır: [ID] <tag> role="..." text="..." placeholder="..." href="..."
Tıklamak veya yazmak için element ID numarasını kullan.

KURALLAR:
- Her yanıtta SADECE TEK BİR JSON nesnesi dön.
- "thought" alanında ne gördüğünü ve neden bu aksiyonu seçtiğini KISA tut.
- Aynı elemente arka arkaya 2 kez tıklama, farklı strateji dene.
- Arama yapmak için: input alanına tıkla → yaz → Enter bas.
- Görev tamamlandığında HEMEN done dön.
- Sayfa yükleniyorsa wait kullan.
- extract aksiyonu sayfadaki tüm görünür metni döndürür.
"""


class BrowserAgent:
    """Playwright tabanlı AI-powered browser agent."""

    def __init__(self, qwen_api):
        self.qwen_api = qwen_api
        self.state = BrowserAgentState.IDLE
        self.task = ""
        self.steps = []
        self.max_steps = 100
        self.current_step = 0
        self.thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._browser = None
        self._page = None
        self._playwright = None
        self._browser_engine = "chromium"
        self._browser_channel = None
        self._browser_label = "Chromium"
        self._use_profile = True
        self._element_map = {}
        self._loop = None
        self._context = None
        self._tmp_profile_dir = None
        self.final_answer = None

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
                "final_answer": self.final_answer,
                "browser_type": self._browser_label,
            }

    def start(self, task, browser_type="chromium", use_profile=False):
        """Start the browser agent with a task.
        
        browser_type format: 'engine:channel' (ör: 'chromium:chrome', 'firefox')
        use_profile: True ise kullanıcının mevcut profili (cookie/hesap) ile açar.
        """
        if self.state == BrowserAgentState.RUNNING:
            return {"error": "Tarayıcı ajanı zaten çalışıyor."}

        self.task = task
        self.steps = []
        self.current_step = 0
        self.state = BrowserAgentState.RUNNING
        self.final_answer = None
        self._use_profile = use_profile
        self._stop_event.clear()

        # browser_type formatını parse et: "chromium:chrome" → engine=chromium, channel=chrome
        if ":" in browser_type:
            parts = browser_type.split(":", 1)
            self._browser_engine = parts[0] if parts[0] in ("firefox", "chromium") else "chromium"
            self._browser_channel = parts[1]
        else:
            self._browser_engine = browser_type if browser_type in ("firefox", "chromium") else "chromium"
            self._browser_channel = None

        # Label oluştur
        channel_labels = {
            "chrome": "Google Chrome", "msedge": "Microsoft Edge",
            "chromium": "Chromium",
        }
        if self._browser_channel:
            self._browser_label = channel_labels.get(self._browser_channel, self._browser_channel)
        elif self._browser_engine == "firefox":
            self._browser_label = "Firefox"
        else:
            self._browser_label = "Chromium"

        self.thread = threading.Thread(target=self._run_agent_thread, daemon=True)
        self.thread.start()
        return {"success": True, "message": f"Tarayıcı ajanı başlatıldı ({self._browser_label})."}

    def stop(self):
        """Stop the running agent."""
        self._stop_event.set()
        self.state = BrowserAgentState.IDLE
        self._add_step("system", "Ajan kullanıcı tarafından durduruldu.", {})
        # Cleanup will happen in the thread
        return {"success": True, "message": "Tarayıcı ajanı durduruldu."}

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
        print(f"[BrowserAgent] Adım {self.current_step}: {action} — {thought[:80]}")

    def _run_agent_thread(self):
        """Thread wrapper that runs the async agent loop."""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._agent_loop())
        except Exception as e:
            print(f"[BrowserAgent] ❌ Thread hatası: {e}")
            self.state = BrowserAgentState.ERROR
            self._add_step("error", str(e), {})
        finally:
            if self._loop:
                self._loop.close()

    async def _agent_loop(self):
        """Ana agent döngüsü: Observe → Think → Act."""
        try:
            await self._launch_browser()
            self._add_step("system", f"{self._browser_label} açıldı", {})

            while True:
                if self._stop_event.is_set():
                    break

                self.current_step += 1

                # 1. OBSERVE — DOM'u çıkar
                dom_text = await self._extract_dom()

                # 2. THINK — Qwen'e gönder
                ai_response = self._ask_qwen(dom_text)
                action_data = self._parse_action(ai_response)

                if not action_data:
                    self._add_step("error", "AI yanıtı parse edilemedi", {"raw": ai_response[:200]})
                    continue

                action = action_data.get("action", "done")
                thought = action_data.get("thought", "")

                # 3. ACT — Aksiyonu uygula
                if action == "done":
                    summary = action_data.get("summary", "")
                    # Sayfadaki metni de al — sonucu chat'e aktarmak için
                    if not summary or len(summary) < 20:
                        try:
                            page_text = await self._page.evaluate("() => document.body.innerText")
                            summary = (page_text or "")[:2000]
                        except:
                            summary = summary or "Görev tamamlandı."
                    self.final_answer = summary
                    self._add_step("done", thought, {"summary": summary[:200]})
                    self.state = BrowserAgentState.DONE
                    break

                if action == "extract":
                    # Sayfadaki metni çıkar ve final_answer'a yaz
                    try:
                        page_text = await self._page.evaluate("() => document.body.innerText")
                        self.final_answer = (page_text or "")[:3000]
                        self._add_step(action, thought, {"chars": len(self.final_answer)})
                    except Exception as e:
                        self._add_step("error", f"Extract hatası: {e}", {})
                    continue

                result = await self._execute_action(action_data)
                self._add_step(action, thought, {**action_data, "result": result})

                # Sayfa yüklenme beklemesi
                if action in ("click", "navigate", "press_key"):
                    await self._wait_for_page_load()

        except Exception as e:
            print(f"[BrowserAgent] Loop hatası: {e}")
            self._add_step("error", str(e), {})
            self.state = BrowserAgentState.ERROR
        finally:
            await self._cleanup()

    def _find_profile_dir(self):
        """Kullanıcının tarayıcı profil klasörünü bul."""
        home = os.path.expanduser("~")
        profile_paths = {
            "chrome": os.path.join(home, ".config", "google-chrome"),
            "chromium": os.path.join(home, ".config", "chromium"),
            "msedge": os.path.join(home, ".config", "microsoft-edge"),
        }
        firefox_dir = os.path.join(home, ".mozilla", "firefox")

        if self._browser_engine == "firefox":
            if os.path.isdir(firefox_dir):
                # Firefox'ta profil klasörü xxxxxxxx.default-release gibi
                for name in os.listdir(firefox_dir):
                    full = os.path.join(firefox_dir, name)
                    if os.path.isdir(full) and "default" in name:
                        return full
            return None
        else:
            channel = self._browser_channel or "chromium"
            path = profile_paths.get(channel)
            if path and os.path.isdir(path):
                return path
            return None

    async def _launch_browser(self):
        """Playwright tarayıcısını başlat — stealth modda."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        engine = self._playwright.firefox if self._browser_engine == "firefox" else self._playwright.chromium

        # Anti-detection argümanları (Chromium tabanlı)
        stealth_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-infobars",
            "--disable-extensions",
        ] if self._browser_engine != "firefox" else []

        context_opts = {
            "viewport": {"width": 1280, "height": 800},
            "locale": "tr-TR",
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }

        if self._use_profile:
            profile_dir = self._find_profile_dir()
            if profile_dir:
                import shutil, tempfile
                tmp_profile = tempfile.mkdtemp(prefix="pardus_browser_")
                self._tmp_profile_dir = tmp_profile

                if self._browser_engine == "firefox":
                    # Firefox: tüm profili kopyala (küçük)
                    shutil.copytree(profile_dir, os.path.join(tmp_profile, "profile"),
                                   dirs_exist_ok=True,
                                   ignore=shutil.ignore_patterns('cache2', 'startupCache',
                                                                  '*.log', 'lock', '.parentlock'))
                    profile_path = os.path.join(tmp_profile, "profile")
                else:
                    # Chrome/Chromium: sadece gerekli dosyaları kopyala (hızlı)
                    parent_dir = os.path.dirname(profile_dir)  # .config/google-chrome
                    default_dst = os.path.join(tmp_profile, "Default")
                    os.makedirs(default_dst, exist_ok=True)

                    # Oturum/cookie dosyaları
                    essential_files = [
                        "Cookies", "Cookies-journal",
                        "Login Data", "Login Data-journal",
                        "Preferences", "Secure Preferences",
                        "Bookmarks", "Favicons", "Favicons-journal",
                        "Web Data", "Web Data-journal",
                        "History", "History-journal",
                    ]
                    default_src = os.path.join(parent_dir, "Default")
                    for fname in essential_files:
                        src = os.path.join(default_src, fname)
                        if os.path.isfile(src):
                            shutil.copy2(src, os.path.join(default_dst, fname))

                    # Local State dosyası (üst dizinde)
                    local_state = os.path.join(parent_dir, "Local State")
                    if os.path.isfile(local_state):
                        shutil.copy2(local_state, os.path.join(tmp_profile, "Local State"))

                    profile_path = tmp_profile

                print(f"[BrowserAgent] Profil hazırlandı: {profile_path}")

                launch_opts = {"headless": False, "args": stealth_args}
                if self._browser_channel:
                    launch_opts["channel"] = self._browser_channel

                context = await engine.launch_persistent_context(
                    profile_path, **launch_opts, **context_opts,
                )
                self._browser = context.browser
                self._page = context.pages[0] if context.pages else await context.new_page()
                self._context = context
                await self._apply_stealth(self._page)
                print(f"[BrowserAgent] {self._browser_label} — profil ile açıldı")
                return
            else:
                print(f"[BrowserAgent] Profil bulunamadı, temiz açılıyor")

        # Temiz tarayıcı
        launch_opts = {"headless": False, "args": stealth_args}
        if self._browser_channel:
            launch_opts["channel"] = self._browser_channel

        self._browser = await engine.launch(**launch_opts)
        context = await self._browser.new_context(**context_opts)
        self._context = context
        self._page = await context.new_page()
        await self._apply_stealth(self._page)
        await self._page.goto("about:blank")
        print(f"[BrowserAgent] {self._browser_label} — temiz profil")

    async def _apply_stealth(self, page):
        """Bot tespitini engelleyen JS enjeksiyonu."""
        stealth_js = """
        // navigator.webdriver'ı gizle
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        
        // Chrome automasyonu property'lerini gizle
        if (window.chrome) {
            window.chrome.runtime = window.chrome.runtime || {};
        }
        
        // Permissions API'yi düzelt
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({state: Notification.permission}) :
                originalQuery(parameters)
        );
        
        // plugins/languages düzelt
        Object.defineProperty(navigator, 'languages', {get: () => ['tr-TR', 'tr', 'en-US', 'en']});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """
        try:
            await page.add_init_script(stealth_js)
        except:
            pass

    async def _cleanup(self):
        """Tarayıcı ve Playwright'ı kapat."""
        try:
            if self._page:
                await self._page.close()
        except:
            pass
        try:
            # Persistent context durumunda context'i kapat
            if hasattr(self, '_context') and self._context:
                await self._context.close()
        except:
            pass
        try:
            if self._browser:
                await self._browser.close()
        except:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except:
            pass
        # Geçici profil klasörünü temizle
        try:
            if hasattr(self, '_tmp_profile_dir') and self._tmp_profile_dir:
                import shutil
                shutil.rmtree(self._tmp_profile_dir, ignore_errors=True)
                self._tmp_profile_dir = None
        except:
            pass
        self._page = None
        self._browser = None
        self._playwright = None
        self._context = None

    async def _extract_dom(self):
        """Sayfadaki interaktif elementleri çıkar — browser-use benzeri DOM extraction."""
        if not self._page:
            return "Sayfa yok."

        url = self._page.url
        title = await self._page.title()

        # Interaktif elementleri çıkaran JS
        elements = await self._page.evaluate("""() => {
            const interactiveTags = ['A', 'BUTTON', 'INPUT', 'TEXTAREA', 'SELECT', 'DETAILS', 'SUMMARY'];
            const interactiveRoles = ['button', 'link', 'textbox', 'searchbox', 'combobox',
                                       'listbox', 'menu', 'menuitem', 'tab', 'checkbox', 'radio',
                                       'switch', 'option', 'slider'];
            const results = [];
            const seen = new Set();

            function isVisible(el) {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return false;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                // Viewport check
                if (rect.bottom < 0 || rect.top > window.innerHeight) return false;
                if (rect.right < 0 || rect.left > window.innerWidth) return false;
                return true;
            }

            function getLabel(el) {
                // aria-label
                let label = el.getAttribute('aria-label') || '';
                // innerText (kısa)
                if (!label) {
                    label = (el.innerText || '').trim().substring(0, 80);
                }
                // value for inputs
                if (!label && el.value) {
                    label = el.value.substring(0, 40);
                }
                // title
                if (!label) {
                    label = el.getAttribute('title') || '';
                }
                return label.replace(/\\n/g, ' ').trim();
            }

            // Tüm interaktif elementleri tara
            const allElements = document.querySelectorAll('*');
            for (const el of allElements) {
                if (results.length >= 150) break;

                const tag = el.tagName;
                const role = el.getAttribute('role') || '';
                const isInteractive = interactiveTags.includes(tag) ||
                                       interactiveRoles.includes(role) ||
                                       el.onclick !== null ||
                                       el.hasAttribute('tabindex') ||
                                       (el.hasAttribute('contenteditable') && el.contentEditable === 'true');

                if (!isInteractive) continue;
                if (!isVisible(el)) continue;

                // Tekrar eden elementleri atla
                const uid = tag + '|' + el.className + '|' + getLabel(el);
                if (seen.has(uid)) continue;
                seen.add(uid);

                const rect = el.getBoundingClientRect();
                results.push({
                    tag: tag.toLowerCase(),
                    role: role || undefined,
                    text: getLabel(el),
                    placeholder: el.getAttribute('placeholder') || undefined,
                    href: el.getAttribute('href') || undefined,
                    type: el.getAttribute('type') || undefined,
                    name: el.getAttribute('name') || undefined,
                    x: Math.round(rect.x + rect.width / 2),
                    y: Math.round(rect.y + rect.height / 2),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                });
            }
            return results;
        }""")

        # Element map oluştur (ID → element info)
        self._element_map = {}
        dom_lines = [f"SAYFA: {title}", f"URL: {url}", f"ELEMENT SAYISI: {len(elements)}", ""]

        for i, el in enumerate(elements, 1):
            self._element_map[i] = el
            parts = [f"[{i}] <{el['tag']}>"]
            if el.get('role'):
                parts.append(f'role="{el["role"]}"')
            if el.get('text'):
                parts.append(f'text="{el["text"][:60]}"')
            if el.get('placeholder'):
                parts.append(f'placeholder="{el["placeholder"]}"')
            if el.get('href'):
                href = el['href'][:60]
                parts.append(f'href="{href}"')
            if el.get('type'):
                parts.append(f'type="{el["type"]}"')
            dom_lines.append(" ".join(parts))

        return "\n".join(dom_lines)

    def _ask_qwen(self, dom_text):
        """DOM bilgisini Qwen'e gönder ve sonraki aksiyonu al."""
        # Son 4 adımı history olarak ekle
        history_text = ""
        if self.steps:
            recent = self.steps[-4:]
            lines = []
            for s in recent:
                detail = s.get("thought", "")
                if "text" in s.get("params", {}):
                    detail += f' → yazıldı: "{s["params"]["text"]}"'
                lines.append(f"Adım {s['step']}: {s['action']} — {detail}")
            history_text = "\nYAPILAN ADIMLAR:\n" + "\n".join(lines)

        prompt = f"""{BROWSER_AGENT_SYSTEM_PROMPT}

GÖREV: {self.task}

{dom_text}
{history_text}

Sonraki TEK aksiyonu JSON olarak dön."""

        try:
            messages = [{"role": "user", "content": prompt}]
            payload = {
                "model": self.qwen_api.DEFAULT_MODEL,
                "messages": messages,
                "stream": False,
            }
            from src.core.qwen_api import QWEN_API_BASE
            r = self.qwen_api._session.post(
                f"{QWEN_API_BASE}/chat/completions",
                json=payload,
                timeout=(10, 120),
            )
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[BrowserAgent] ❌ Qwen hatası: {e}")
            return json.dumps({"action": "done", "summary": f"API hatası: {e}", "thought": "API hatası"})

    def _parse_action(self, response):
        """AI yanıtından JSON aksiyonu parse et."""
        response = response.strip()

        # Düz JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # JSON bloğu bul
        m = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

        # Code block içinde
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # Regex kurtarma
        action_match = re.search(r'"action"\s*:\s*"([^"]+)"', response)
        if action_match:
            action = action_match.group(1)
            result = {"action": action, "thought": "Regex kurtarma"}
            id_match = re.search(r'"element_id"\s*:\s*(\d+)', response)
            text_match = re.search(r'"text"\s*:\s*"([^"]*)"', response)
            url_match = re.search(r'"url"\s*:\s*"([^"]*)"', response)
            if id_match:
                result["element_id"] = int(id_match.group(1))
            if text_match:
                result["text"] = text_match.group(1)
            if url_match:
                result["url"] = url_match.group(1)
            return result

        return None

    async def _execute_action(self, action_data):
        """Playwright üzerinden aksiyonu çalıştır."""
        action = action_data.get("action", "")
        page = self._page
        if not page:
            return "Sayfa yok"

        try:
            if action == "navigate":
                url = action_data.get("url", "")
                if url and not url.startswith("http"):
                    url = "https://" + url
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                return f"Navigated to {url}"

            elif action == "click":
                el_id = action_data.get("element_id")
                if el_id and el_id in self._element_map:
                    el = self._element_map[el_id]
                    await page.mouse.click(el["x"], el["y"])
                    return f"Clicked element {el_id} at ({el['x']}, {el['y']})"
                return "Element bulunamadı"

            elif action == "type":
                el_id = action_data.get("element_id")
                text = action_data.get("text", "")
                if el_id and el_id in self._element_map:
                    el = self._element_map[el_id]
                    await page.mouse.click(el["x"], el["y"])
                    await asyncio.sleep(0.3)
                    # Mevcut içeriği temizle
                    await page.keyboard.press("Control+a")
                    await asyncio.sleep(0.1)
                    await page.keyboard.type(text, delay=30)
                    return f"Typed '{text}' into element {el_id}"
                return "Element bulunamadı"

            elif action == "press_key":
                key = action_data.get("key", "Enter")
                await page.keyboard.press(key)
                return f"Pressed {key}"

            elif action == "scroll":
                direction = action_data.get("direction", "down")
                amount = action_data.get("amount", 500)
                delta = amount if direction == "down" else -amount
                await page.mouse.wheel(0, delta)
                return f"Scrolled {direction} {amount}px"

            elif action == "wait":
                seconds = min(action_data.get("seconds", 2), 10)
                await asyncio.sleep(seconds)
                return f"Waited {seconds}s"

            elif action == "extract":
                text = await page.evaluate("() => document.body.innerText")
                # İlk 3000 karakter
                text = (text or "")[:3000]
                self.final_answer = text
                return f"Extracted {len(text)} chars"

            elif action == "back":
                await page.go_back()
                return "Went back"

            else:
                return f"Bilinmeyen aksiyon: {action}"

        except Exception as e:
            print(f"[BrowserAgent] ❌ Aksiyon hatası ({action}): {e}")
            return f"Hata: {str(e)[:100]}"

    async def _wait_for_page_load(self):
        """Sayfa yüklenmesini bekle."""
        try:
            await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
        except:
            pass
        await asyncio.sleep(0.5)
