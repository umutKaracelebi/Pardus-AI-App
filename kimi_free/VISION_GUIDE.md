# Kimi Free API — Vision (Görsel Analiz) Kullanım Kılavuzu

## API Bilgileri

- **Endpoint:** `http://localhost:8001/v1/chat/completions`
- **Format:** OpenAI ChatGPT Vision API ile %100 uyumlu
- **Yetkilendirme:** `Authorization: Bearer <refresh_token>`

## Görsel Gönderme Yöntemleri

### Yöntem 1: URL ile Görsel Gönderme

Eğer görselin internet üzerinde erişilebilir bir URL'si varsa:

```json
{
  "model": "kimi",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "image_url",
          "image_url": {
            "url": "https://ornek.com/gorsel.jpg"
          }
        },
        {
          "type": "text",
          "text": "Bu görselde ne var? Detaylı açıkla."
        }
      ]
    }
  ],
  "use_search": false,
  "stream": false
}
```

### Yöntem 2: Base64 ile Lokal Dosya Gönderme

Eğer görsel lokal dosya sisteminde ise, önce base64'e çevir, sonra `data:` URI olarak gönder:

**Adım 1 — Dosyayı base64'e çevir:**
```bash
B64=$(base64 -w0 /dosya/yolu/gorsel.png)
```

**Adım 2 — API'ye gönder:**
```json
{
  "model": "kimi",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,<BASE64_STRING>"
          }
        },
        {
          "type": "text",
          "text": "Bu görseli açıkla."
        }
      ]
    }
  ],
  "use_search": false,
  "stream": false
}
```

**Desteklenen MIME tipleri:**
- `data:image/png;base64,...`
- `data:image/jpeg;base64,...`
- `data:image/webp;base64,...`
- `data:image/gif;base64,...`

### Yöntem 3: PDF / Dosya Gönderme

PDF ve diğer dosyalar için `file` tipi kullan:

```json
{
  "model": "kimi",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "file",
          "file_url": {
            "url": "https://ornek.com/dosya.pdf"
          }
        },
        {
          "type": "text",
          "text": "Bu dosyayı özetle."
        }
      ]
    }
  ],
  "use_search": false,
  "stream": false
}
```

Base64 ile lokal PDF:
```json
{
  "type": "file",
  "file_url": {
    "url": "data:application/pdf;base64,<BASE64_STRING>"
  }
}
```

## Tam curl Örnekleri

### URL ile Görsel Analizi
```bash
curl http://localhost:8001/v1/chat/completions \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kimi",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "image_url", "image_url": {"url": "https://ornek.com/gorsel.jpg"}},
        {"type": "text", "text": "Bu görselde ne var?"}
      ]
    }],
    "use_search": false,
    "stream": false
  }'
```

### Base64 ile Lokal Görsel Analizi
```bash
B64=$(base64 -w0 /yol/gorsel.png)
curl http://localhost:8001/v1/chat/completions \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"kimi\",
    \"messages\": [{
      \"role\": \"user\",
      \"content\": [
        {\"type\": \"image_url\", \"image_url\": {\"url\": \"data:image/png;base64,$B64\"}},
        {\"type\": \"text\", \"text\": \"Bu görseli açıkla.\"}
      ]
    }],
    \"use_search\": false,
    \"stream\": false
  }"
```

## Node.js / JavaScript ile Kullanım

```javascript
const fs = require('fs');
const path = require('path');

async function analyzeImage(imagePath, prompt) {
  const imageBuffer = fs.readFileSync(imagePath);
  const base64 = imageBuffer.toString('base64');
  const ext = path.extname(imagePath).slice(1); // png, jpg, etc.
  const mimeType = ext === 'jpg' ? 'jpeg' : ext;

  const response = await fetch('http://localhost:8001/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer TOKEN',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: 'kimi',
      messages: [{
        role: 'user',
        content: [
          { type: 'image_url', image_url: { url: `data:image/${mimeType};base64,${base64}` } },
          { type: 'text', text: prompt }
        ]
      }],
      use_search: false,
      stream: false
    })
  });

  const data = await response.json();
  return data.choices[0].message.content;
}

// Kullanım:
// const result = await analyzeImage('/yol/gorsel.png', 'Bu görselde ne var?');
```

## Python ile Kullanım

```python
import base64
import requests

def analyze_image(image_path, prompt, token):
    with open(image_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()

    ext = image_path.rsplit('.', 1)[-1]
    mime = 'jpeg' if ext == 'jpg' else ext

    response = requests.post(
        'http://localhost:8001/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        json={
            'model': 'kimi',
            'messages': [{
                'role': 'user',
                'content': [
                    {'type': 'image_url', 'image_url': {'url': f'data:image/{mime};base64,{b64}'}},
                    {'type': 'text', 'text': prompt}
                ]
            }],
            'use_search': False,
            'stream': False
        }
    )

    return response.json()['choices'][0]['message']['content']

# Kullanım:
# result = analyze_image('/yol/gorsel.png', 'Bu görselde ne var?', 'TOKEN')
```

## Önemli Notlar

1. **`use_search: false`** — Görsel analizde internet aramasını kapat, sonuçları etkileyebilir
2. **URL erişilebilirliği** — URL ile gönderilen görseller Kimi sunucularından erişilebilir olmalı (403/404 veren URL'ler çalışmaz)
3. **Base64 boyutu** — Çok büyük dosyalar (>10MB) sorun çıkarabilir
4. **Görsel + metin birlikte** — `content` dizisinde hem `image_url` hem `text` olmalı
5. **Model adı** — `"model": "kimi"` yeterli, özel model belirtmeye gerek yok
6. **Proxy kullanımı** — 429 koruması için `localhost:8002` üzerinden de kullanılabilir
