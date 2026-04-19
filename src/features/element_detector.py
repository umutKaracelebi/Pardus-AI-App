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
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Canny edge detection ile kenarları bul
        edges = cv2.Canny(gray, 50, 150)
        
        # Dilation ile birbirine yakın harfleri/kenarları birleştir
        # Yatayda daha geniş (18), dikeyde daha dar (8) birleştirme
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (18, 8))
        dilated = cv2.dilate(edges, kernel, iterations=1)
        
        # Konturları bul
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        element_dict = {}
        element_id = 1
        
        # Yukarıdan aşağıya, soldan sağa numaralandırmak için sırala
        # Y koordinatını 40 piksellik bantlara bölüyoruz ki aynı satırdakiler düzgün sıralansın
        bounding_boxes = [cv2.boundingRect(c) for c in contours]
        bounding_boxes.sort(key=lambda b: (b[1] // 40, b[0]))
        
        for x, y, w, h in bounding_boxes:
            # Çok küçük (gürültü) veya çok büyük (tüm ekran) olanları yoksay
            if w < 12 or h < 12 or w > img.shape[1] * 0.8 or h > img.shape[0] * 0.8:
                continue
                
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
            
            (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
            
            # Etiket kutusu koordinatları (hedefin sol üst köşesine)
            bg_x1, bg_y1 = x, max(0, y - th - 5)
            bg_x2, bg_y2 = x + tw + 4, max(th + 5, y)
            
            cv2.rectangle(img, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), -1)
            cv2.putText(img, label, (x + 2, max(th + 2, y - 3)), font, font_scale, (0, 255, 255), thickness)
            
            element_id += 1
            if element_id > 300: # Ekranda aşırı kalabalık olmasını önle
                break
                
        cv2.imwrite(dst_path, img)
        print(f"[SoM] {len(element_dict)} adet element tespit edildi.")
        return element_dict
