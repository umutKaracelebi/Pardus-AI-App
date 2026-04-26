import os
try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

class ElementDetector:
    """
    Set-of-Mark (SoM) tabanlı element tespiti.
    OpenCV kullanarak ekrandaki butonları, ikonları ve metinleri bulup numaralandırır.
    """
    
    def __init__(self):
        pass
        
    def detect_and_draw(self, src_path, dst_path):
        """
        Resmi analiz eder, tespit ettiği öğeleri dst_path'e kaydeder
        ve ID -> (X,Y) sözlüğü döndürür.
        """
        if not HAS_OPENCV:
            print("[SoM] OpenCV bulunamadı! Lütfen kurun: pip install opencv-python-headless numpy")
            return {}
            
        img = cv2.imread(src_path)
        if img is None:
            return {}
        
        img_h, img_w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Canny edge detection ile kenarları bul
        edges = cv2.Canny(gray, 50, 150)
        
        # Dilation ile birbirine yakın harfleri/kenarları birleştir
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (18, 8))
        dilated = cv2.dilate(edges, kernel, iterations=1)
        
        # Konturları bul
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # === İKİNCİ GEÇİŞ: Düşük kontrastlı büyük kartlar için ===
        # Bilateral filter + Canny (daha hassas)
        blur = cv2.bilateralFilter(gray, 9, 75, 75)
        edges2 = cv2.Canny(blur, 20, 80)
        kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT, (12, 6))
        dilated2 = cv2.dilate(edges2, kernel2, iterations=1)
        # RETR_TREE: iç içe konturları da bul (büyük beyaz alanın içindeki kartlar)
        contours2, _ = cv2.findContours(dilated2, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        # Tüm bounding box'ları topla
        all_rects = set()
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            all_rects.add((x, y, w, h))
        for c in contours2:
            x, y, w, h = cv2.boundingRect(c)
            # Sadece orta-büyük olanları ekle (küçükleri birinci geçiş bulmuştur)
            if w > 60 and h > 40:
                all_rects.add((x, y, w, h))
        
        bounding_boxes = list(all_rects)
        
        element_dict = {}
        element_id = 1
        
        # Yukarıdan aşağıya, soldan sağa numaralandırmak için sırala
        bounding_boxes.sort(key=lambda b: (b[1] // 40, b[0]))
        
        # Overlap kontrolü için kabul edilmiş kutular
        accepted = []
        
        for x, y, w, h in bounding_boxes:
            # Çok küçük (gürültü) — minimum 20x15 piksel
            if w < 20 or h < 15:
                continue
            # Çok büyük (tüm ekran veya büyük panel) — %80'den geniş
            if w > img_w * 0.80 or h > img_h * 0.80:
                continue
            # Dock bölgesini atla (ekranın en altı, y > %92)
            if y + h > img_h * 0.92:
                continue
            # Çok ince/uzun elemanları atla (aspect ratio kontrolü)
            aspect = w / max(h, 1)
            if aspect > 15 or aspect < 0.06:
                continue
            
            # Overlap kontrolü: kabul edilmiş kutularla %60+ örtüşme varsa atla
            cx, cy = x + w // 2, y + h // 2
            skip = False
            for ax, ay, aw, ah in accepted:
                # Merkez kabul edilmiş kutunun içinde mi?
                if ax <= cx <= ax + aw and ay <= cy <= ay + ah:
                    skip = True
                    break
            if skip:
                continue
            
            accepted.append((x, y, w, h))
                
            # Kutuyu çiz
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 200, 0), 2)
            
            # Merkezin koordinatı
            cx = x + w // 2
            cy = y + h // 2
            element_dict[element_id] = {"x": cx, "y": cy}
            
            # Etiketi yaz (Siyah arka plan üzerine sarı yazı)
            label = f"[{element_id}]"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 2
            
            (tw, th_text), _ = cv2.getTextSize(label, font, font_scale, thickness)
            
            bg_x1, bg_y1 = x, max(0, y - th_text - 5)
            bg_x2, bg_y2 = x + tw + 4, max(th_text + 5, y)
            
            cv2.rectangle(img, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), -1)
            cv2.putText(img, label, (x + 2, max(th_text + 2, y - 3)), font, font_scale, (0, 255, 255), thickness)
            
            element_id += 1
            if element_id > 60:  # Maksimum 60 element
                break
                
        cv2.imwrite(dst_path, img)
        print(f"[SoM] {len(element_dict)} adet element tespit edildi.")
        return element_dict
