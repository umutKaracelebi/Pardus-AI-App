#!/bin/bash
# Pardus AI Agent — /dev/uinput kalıcı izin düzeltmesi
# Bu script bir kez sudo ile çalıştırılmalıdır:
#   sudo bash fix_uinput.sh

set -e

echo "🔧 /dev/uinput kalıcı izin ayarları yapılıyor..."

# 1. uinput modülünü şimdi yükle
modprobe uinput 2>/dev/null || true

# 2. Boot'ta otomatik yüklenmesi için modül listesine ekle
if ! grep -q "^uinput" /etc/modules-load.d/*.conf 2>/dev/null; then
    echo "uinput" > /etc/modules-load.d/uinput.conf
    echo "   ✅ /etc/modules-load.d/uinput.conf oluşturuldu"
fi

# 3. Udev kuralı — modül yüklendiğinde izinleri ayarla
cat > /etc/udev/rules.d/99-pardus-uinput.rules << 'EOF'
SUBSYSTEM=="misc", KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"
EOF
echo "   ✅ /etc/udev/rules.d/99-pardus-uinput.rules oluşturuldu"

# 4. Udev kurallarını yeniden yükle
udevadm control --reload-rules
udevadm trigger /dev/uinput 2>/dev/null || true

# 5. Anlık izin (hemen çalışsın)
chmod 660 /dev/uinput
chown root:input /dev/uinput

echo ""
echo "✅ Tamamlandı! Kontrol:"
ls -la /dev/uinput
echo ""
echo "Bu ayar yeniden başlatmalarda da kalıcı olacak."
