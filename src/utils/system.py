import subprocess
import os
from termcolor import colored

class SystemUtils:
    def __init__(self):
        self.unsafe_commands = ["rm -rf /", "mkfs", ":(){ :|:& };:"] # Çok tehlikeli kalıplar

    def run_command(self, command):
        """
        Komutu çalıştırmadan önce güvenlik kontrolü yapar ve kullanıcıya onay sorar.
        """
        if not command:
            return "Boş komut."

        # Basit güvenlik filtresi (Geliştirilebilir)
        for unsafe in self.unsafe_commands:
            if unsafe in command:
                return f"GÜVENLİK UYARISI: '{command}' komutu çok tehlikeli olduğu için engellendi!"

        print(colored(f"\n⚠️  ONAY: Şu komut çalıştırılacak: {command}", "yellow", attrs=["bold"]))
        approval = input("Onaylıyor musunuz? (e/h): ").lower().strip()

        if approval in ["e", "evet", "y", "yes"]:
            try:
                # Komutu çalıştır ve çıktısını al
                result = subprocess.run(
                    command, 
                    shell=True,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    executable="/bin/bash" 
                )
                
                output = result.stdout
                if result.stderr:
                    output += f"\nSTDERR:\n{result.stderr}"
                
                return output.strip() if output.strip() else "Komut başarıyla çalıştırıldı (Çıktı yok)."
            
            except Exception as e:
                return f"HATA: Komut çalıştırılamadı: {str(e)}"
        else:
            return "İşlem kullanıcı tarafından iptal edildi."
