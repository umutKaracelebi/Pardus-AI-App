import argparse
import sys
import os
import threading

# Check if running in the virtual environment
if not hasattr(sys, 'real_prefix') and (not hasattr(sys, 'base_prefix') or sys.base_prefix == sys.prefix):
    venv_python = os.path.join(os.path.dirname(__file__), "venv/bin/python3")
    if os.path.exists(venv_python) and sys.executable != venv_python:
        print("⚠️  Sanal ortam (venv) algılanamadı. Otomatik olarak venv üzerinden yeniden başlatılıyor...")
        os.execv(venv_python, [venv_python] + sys.argv)
    else:
        print("❌ HATA: Sanal ortam bulunamadı. Lütfen kurulumun tam olduğunu kontrol edin.")
        sys.exit(1)

# Lazy imports — ağır modüller sadece gerektiğinde yüklenir
# from src.core.model_loader import ModelLoader  -> sadece --local/--load-test
# from src.interface.cli import CLI              -> sadece CLI modunda

def start_qwen_gateway(blocking=False):
    """qwen-free-api sunucusunu başlat (port 3264).
    
    blocking=False: Arka planda başlatır, UI'ı bloklamaz (varsayılan).
    blocking=True:  Hazır olana kadar bekler (CLI modu için).
    """
    import subprocess
    import time
    import requests

    QWEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qwen_free")
    
    # qwen-free-api kontrol (port 3264)
    try:
        r = requests.get("http://localhost:3264/api/status", timeout=2)
        if r.status_code == 200:
            print("   ✅ qwen-free-api zaten çalışıyor (port 3264)")
            return
    except Exception:
        pass

    print("   🚀 qwen-free-api başlatılıyor (port 3264)...")
    env = os.environ.copy()
    env["SKIP_ACCOUNT_MENU"] = "true"
    env["PORT"] = "3264"
    subprocess.Popen(
        ["node", "index.js"],
        cwd=QWEN_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env
    )

    if not blocking:
        # Arka planda başlat — UI'ı bekleme, hazır olunca API çağrıları zaten retry yapar
        print("   ⏳ qwen-free-api arka planda başlatıldı, hazır olunca bağlanacak.")
        return

    # CLI modu: hazır olana kadar bekle
    for i in range(15):
        time.sleep(1)
        try:
            r = requests.get("http://localhost:3264/api/status", timeout=2)
            if r.status_code == 200:
                print("   ✅ qwen-free-api hazır! (port 3264)")
                return
        except Exception:
            pass
    print("   ⚠️ qwen-free-api henüz hazır değil, yine de devam ediliyor...")

def start_gui():
    """Start the Flask + PyWebView GUI."""
    import webview
    from src.interface.gui.app_server import app, start_server

    PORT = 5789

    # Start Flask server in a background thread
    server_thread = threading.Thread(target=start_server, args=(PORT,), daemon=True)
    server_thread.start()

    import time
    time.sleep(0.3)

    # Qwen API kontrolünü YAPMA — gateway arka planda başlıyor,
    # API çağrıları zaten retry mekanizmasına sahip (qwen_api.py MAX_RETRIES).
    # Bu sayede pencere anında açılıyor.

    # Create and start PyWebView window
    window = webview.create_window(
        title='Pardus AI Asistanı',
        url=f'http://127.0.0.1:{PORT}',
        width=1050,
        height=720,
        min_size=(800, 550),
        background_color='#0d1117',
        text_select=True
    )

    # Agent'ın pencereyi küçültebilmesi için referansı sakla
    import src.interface.gui.app_server as srv
    srv._webview_window = window

    icon_path = os.path.join(os.path.dirname(__file__), 'pardusaiapplogo.png')
    webview.start(icon=icon_path, debug=False)

def main():
    parser = argparse.ArgumentParser(description="Pardus AI Asistanı")
    parser.add_argument("--cli", action="store_true", help="Terminal (CLI) arayüzünü başlat")
    parser.add_argument("--chat", action="store_true", help="Terminal modunu başlat (geriye dönük uyumluluk)")
    parser.add_argument("--local", action="store_true", help="Yerel Qwen2-VL modelini kullan")
    parser.add_argument("--load-test", action="store_true", help="Model yükleme testi yap")

    args = parser.parse_args()

    if args.load_test:
        print("Model yükleme testi başlatılıyor...")
        from src.core.model_loader import ModelLoader
        loader = ModelLoader()
        model, processor = loader.load_model()
        if model and processor:
            print("✓ TEST BAŞARILI: Model ve Processor belleğe yüklendi.")
            print(f"  Model tipi: {type(model).__name__}")
            print(f"  Cihaz: {model.device}")
        else:
            print("✗ TEST BAŞARISIZ: Model veya Processor yüklenemedi.")
        return

    # Qwen gateway başlat (local mod hariç)
    if not args.local:
        is_gui = not (args.cli or args.chat)
        print("📡 Qwen AI gateway başlatılıyor...")
        if is_gui:
            # GUI modu: arka planda başlat, pencereyi bloklamadan
            threading.Thread(target=start_qwen_gateway, kwargs={'blocking': False}, daemon=True).start()
        else:
            # CLI modu: hazır olana kadar bekle
            start_qwen_gateway(blocking=True)

    if args.cli or args.chat or args.local:
        from src.interface.cli import CLI
        mode = "local" if args.local else "cloud"
        cli = CLI(mode=mode)
        cli.start()
    else:
        print("🚀 Pardus AI Web Arayüzü başlatılıyor...")
        try:
            start_gui()
        except Exception as e:
            print(f"❌ GUI başlatılırken hata oluştu: {str(e)}")
            print("ℹ️  Alternatif olarak Terminal CLI başlatılıyor...")
            from src.interface.cli import CLI
            cli = CLI(mode="cloud")
            cli.start()

if __name__ == "__main__":
    main()
