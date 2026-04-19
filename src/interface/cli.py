from src.utils.system import SystemUtils
import re
from termcolor import colored
import os
import time
from src.core.model_loader import ModelLoader
from src.features.screen_capture import ScreenCapture
from src.features.document_editor import DocumentEditor
from src.core.qwen_api import QwenAPI
from qwen_vl_utils import process_vision_info

class CLI:
    def __init__(self, mode="cloud"):
        self.mode = mode
        self.loader = ModelLoader()
        self.sys_utils = SystemUtils()
        self.doc_editor = DocumentEditor()
        self.qwen_api = QwenAPI()
        self.model = None
        self.processor = None

    def start(self):
        print(colored("╔═══════════════════════════════════════════╗", "cyan", attrs=["bold"]))
        if self.mode == "cloud":
             print(colored("║   Pardus AI Asistanı (Cloud Modu)        ║", "cyan", attrs=["bold"]))
        else:
             print(colored("║   Pardus AI Asistanı (Yerel Qwen2-VL)    ║", "cyan", attrs=["bold"]))
        print(colored("╚═══════════════════════════════════════════╝", "cyan", attrs=["bold"]))
        
        if self.mode == "local":
            self.model, self.processor = self.loader.load_model()
            
            if not self.model or not self.processor:
                print(colored("✗ Model yüklenemediği için çıkış yapılıyor.", "red"))
                return
        else:
            print(colored("✓ Cloud AI modunda başlatıldı. Hafif ve hızlı!", "green"))

        print(colored("\n📝 Kullanım:", "yellow", attrs=["bold"]))
        print(colored("  • Görüntü ile: /image /yol/goruntu.jpg Soru?", "white"))
        print(colored("  • Ekran Görüntüsü: /screenshot Soru?", "white"))
        print(colored("  • Komut Üret: /cmd Dosyaları listele", "white"))
        print(colored("  • Belge Düzenle: /doc /yol/dosya.txt Talimat", "white"))
        print(colored("  • Sadece metin: Merhaba, nasılsın?", "white"))
        print(colored("  • Çıkış: q, exit, çıkış\n", "white"))
        
        # Bekleyen komut onayı için durum değişkeni
        self.pending_command = None
        self.pending_doc_save = None

        while True:
            try:
                # readline satır kaymasını önlemek için ANSI renk kodlarını \001 ve \002 ile sarıyoruz
                prompt = "\001\033[1;33m\002Siz: \001\033[0m\002"
                user_input = input(prompt)
                
                if not user_input.strip():
                    continue

                if user_input.lower().strip() in ["q", "exit", "çıkış"]:
                    print(colored("👋 Görüşmek üzere!", "green"))
                    break
                
                if getattr(self, "pending_doc_save", None):
                    if user_input.lower().strip() in ["e", "evet", "y", "yes", "onay"]:
                        file_path = self.pending_doc_save["file"]
                        content = self.pending_doc_save["content"]
                        try:
                            self.doc_editor.write_file(file_path, content)
                            print(colored(f"✅ Değişiklikler {file_path} dosyasına kaydedildi.", "green"))
                        except Exception as e:
                            print(colored(f"✗ Dosya kaydedilirken hata oluştu: {e}", "red"))
                    else:
                        print(colored("ℹ️  Değişiklikler kaydedilmedi.", "yellow"))
                    
                    self.pending_doc_save = None
                    continue
                
                # Eğer bekleyen bir komut varsa ve kullanıcı "evet" dediyse
                if self.pending_command:
                    if user_input.lower().strip() in ["e", "evet", "y", "yes", "onay"]:
                        output = self.sys_utils.run_command(self.pending_command)
                        print(colored(f"⚙️ Sistem: \n{output}", "magenta"))
                    else:
                        print(colored("ℹ️  Komut çalıştırılmadı.", "yellow"))
                    
                    self.pending_command = None
                    continue

                self.generate_response(user_input)
                
            except KeyboardInterrupt:
                print(colored("\n\n👋 Çıkış yapılıyor...", "yellow"))
                break
            except Exception as e:
                print(colored(f"✗ Hata: {str(e)}", "red"))
                import traceback
                traceback.print_exc()

    def generate_response(self, user_input):
        if self.mode == "local" and (not self.model or not self.processor):
            return

        messages = [
            {
                "role": "user",
                "content": []
            }
        ]
        
        # Ekran Görüntüsü: /screenshot Soru
        if user_input.startswith("/screenshot"):
            prompt = user_input[11:].strip()
            if not prompt:
                prompt = "Bu ekranda ne görüyorsun?"
            
            print(colored("📸 Ekran görüntüsü alınıyor...", "cyan"))
            # CLI'ın ekrandan çekilmesi için kısa süre bekle
            time.sleep(1)
            
            capturer = ScreenCapture()
            screenshot_path = capturer.capture_full_screen("current_screen.png")
            
            if screenshot_path:
                print(colored(f"✅ Ekran görüntüsü kaydedildi: {screenshot_path}", "green"))
                messages[0]["content"].append({"type": "image", "image": f"file://{os.path.abspath(screenshot_path)}"})
                messages[0]["content"].append({"type": "text", "text": prompt})
            else:
                print(colored("✗ Ekran görüntüsü alınamadı.", "red"))
                return

        # Komut Üretme: /cmd Soru
        elif user_input.startswith("/cmd "):
            query = user_input[5:].strip()
            
            # Basit bir system prompt ile modelden komut iste
            cmd_prompt = (
                "Sen bir Linux terminal asistanısın. Kullanıcının isteğini yerine getirecek "
                "TEK BİR Linux komutu yaz. Başka hiçbir açıklama yapma. "
                "Sadece komutu çıktı olarak ver.\n"
                f"İstek: {query}"
            )
            messages[0]["content"].append({"type": "text", "text": cmd_prompt})

        # Belge Düzenleme: /doc /yol/dosya.txt Talimat
        elif user_input.startswith("/doc ") or user_input.startswith("/edit "):
            cmd = "/doc " if user_input.startswith("/doc ") else "/edit "
            parts = user_input[len(cmd):].split(maxsplit=1)
            
            if len(parts) < 2:
                print(colored(f"✗ Kullanım: {cmd}/yol/dosya.txt Talimat", "red"))
                return
            
            file_path = parts[0]
            instructions = parts[1]
            
            try:
                file_content = self.doc_editor.read_file(file_path)
            except Exception as e:
                print(colored(f"✗ Dosya okunamadı: {e}", "red"))
                return
                
            doc_prompt = (
                f"Bir dosyanın mevcut içeriği aşağıdadır:\n\n"
                f"--- MEVCUT DOSYA İÇERİĞİ ---\n"
                f"{file_content}\n"
                f"----------------------------\n\n"
                f"KULLANICI TALİMATI: {instructions}\n\n"
                f"Görev: Kullanıcının talimatını uygulayarak dosyanın yeni halini oluştur.\n"
                f"Lütfen SADECE dosyanın yeni ve tam içeriğini yaz. Başka hiçbir açıklama yapma.\n"
                f"Yeni içeriği KESİNLİKLE <file_content> ve </file_content> etiketleri arasına koy."
            )
            messages[0]["content"].append({"type": "text", "text": doc_prompt})
            self.current_doc_file = file_path

        # Görüntü komutu kontrolü: /image /path/to/image.jpg Prompt
        elif user_input.startswith("/image "):
            parts = user_input[7:].split(maxsplit=1)
            
            if len(parts) < 2:
                print(colored("✗ Kullanım: /image /yol/goruntu.jpg Soru?", "red"))
                return
            
            image_path, prompt = parts
            
            if not os.path.exists(image_path):
                print(colored(f"✗ Görüntü bulunamadı: {image_path}", "red"))
                return
            
            messages[0]["content"].append({"type": "image", "image": f"file://{os.path.abspath(image_path)}"})
            messages[0]["content"].append({"type": "text", "text": prompt})
            print(colored("🖼️  Görüntü analiz ediliyor...", "cyan"))
        else:
            messages[0]["content"].append({"type": "text", "text": user_input})

        try:
            if self.mode == "cloud":
                has_image = any(msg.get("type") == "image" for msg in messages[0]["content"])
                if has_image:
                    text_prompt = ""
                    image_path = ""
                    for msg in messages[0]["content"]:
                        if msg["type"] == "text":
                            text_prompt += msg["text"] + " "
                        elif msg["type"] == "image":
                            image_path = msg["image"].replace("file://", "")
                    
                    try:
                        response = self.qwen_api.generate_vision_response(text_prompt.strip(), os.path.abspath(image_path))
                    except Exception as e:
                        print(colored(f"❌ Vision Hatası: {str(e)}", "red"))
                        return
                else:
                    # Qwen API metin çözümü
                    print(colored("☁️  Qwen AI üzerinden yanıt bekleniyor...", "grey"))
                    response = self.qwen_api.generate_response(messages)
            else:
                # Yerel model üzerinde koştur
                text = self.processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                image_inputs, video_inputs = process_vision_info(messages)
                inputs = self.processor(
                    text=[text],
                    images=image_inputs,
                    videos=video_inputs,
                    padding=True,
                    return_tensors="pt",
                )
                inputs = inputs.to(self.model.device)

                # Inference
                generated_ids = self.model.generate(**inputs, max_new_tokens=512)
                generated_ids_trimmed = [
                    out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                ]
                response = self.processor.batch_decode(
                    generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
                )[0]
            
            # İçerik Çıkarma (<file_content> etiketlerini ara)
            import re
            
            if getattr(self, "current_doc_file", None):
                # Sadece belge düzenlemede özel parse işlemi
                content_match = re.search(r"<file_content>\n?(.*?)\n?</file_content>", response, re.DOTALL)
                if content_match:
                    parsed_response = content_match.group(1)
                else:
                    # Fallback (Eğer model etiketi koymayı unuttuysa eski markdown temizliğini yap)
                    parsed_response = response.replace("```bash", "").replace("```sh", "").replace("```", "").strip()
                    # Bilinen konuşma kalıplarını temizle
                    parsed_response = re.sub(r"^(İşte dosyanın yeni hali:|İşte yeni içerik:|İşte istenen dosya içeriği:|Aşağıda dosyanın yeni hali bulunmaktadır:)\n+", "", parsed_response).strip()
                
                print(colored(f"🤖 Asistan (Değişiklik Önizleme):\n{parsed_response}", "cyan"))
                print(colored(f"\n💡 Bu değişiklikleri {self.current_doc_file} dosyasına kaydetmek ister misiniz? (evet/hayır)", "yellow"))
                self.pending_doc_save = {"file": self.current_doc_file, "content": parsed_response}
                self.current_doc_file = None
            else:
                # Normal sohbet veya komut için markdown temizliği
                code_block_match = re.search(r"```[a-zA-Z]*\n(.*?)```", response, re.DOTALL)
                if code_block_match and user_input.startswith("/cmd"):
                    response = code_block_match.group(1).strip()
                else:
                    response = response.replace("```bash", "").replace("```sh", "").replace("```", "").strip()
                
                print(colored(f"🤖 Asistan: \n{response}", "blue", attrs=["bold"]))
                
                if user_input.startswith("/cmd ") or response.strip().startswith("sudo") or (len(response.split()) < 10 and "\n" not in response and (" ls " in f" {response} " or response.strip().startswith("ls"))):
                     print(colored("\n💡 Bu bir komut gibi görünüyor. Çalıştırmak ister misiniz? (evet/hayır)", "yellow"))
                     self.pending_command = response.strip()

        except Exception as e:
            print(colored(f"✗ İşlem sırasında hata: {str(e)}", "red"))
