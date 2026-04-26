#!/bin/bash
# Kimi Free API — Stres Testi
# Proxy'nin rate limiting korumasını test eder

API_URL="${1:-http://localhost:8002}"
TOKEN="${2}"
TOTAL_REQUESTS="${3:-10}"

if [ -z "$TOKEN" ]; then
  echo "❌ Kullanım: ./stress_test.sh [API_URL] <TOKEN> [TOPLAM_İSTEK]"
  echo "   Örnek: ./stress_test.sh http://localhost:8002 eyJhbG... 10"
  exit 1
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     Kimi API Stres Testi                 ║"
echo "╠══════════════════════════════════════════╣"
echo "║  API:     $API_URL"
echo "║  İstek:   $TOTAL_REQUESTS adet"
echo "╚══════════════════════════════════════════╝"
echo ""

SUCCESS=0
FAILED=0
RATE_LIMITED=0

for i in $(seq 1 $TOTAL_REQUESTS); do
  echo -n "[$i/$TOTAL_REQUESTS] Gönderiliyor... "
  
  START=$(date +%s%N)
  
  RESPONSE=$(curl -s -w "\n%{http_code}" "$API_URL/v1/chat/completions" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"kimi\",\"messages\":[{\"role\":\"user\",\"content\":\"$i sayısının karesi nedir? Sadece sayıyı yaz.\"}],\"stream\":false}" \
    --max-time 120)
  
  END=$(date +%s%N)
  DURATION=$(( (END - START) / 1000000 ))
  
  HTTP_CODE=$(echo "$RESPONSE" | tail -1)
  BODY=$(echo "$RESPONSE" | head -n -1)
  
  if [ "$HTTP_CODE" = "200" ]; then
    # Kimi hata kodu kontrol
    ERROR_CODE=$(echo "$BODY" | grep -o '"code":-[0-9]*' | head -1)
    if [ -n "$ERROR_CODE" ]; then
      echo "⚠️  Kimi hatası: $ERROR_CODE (${DURATION}ms)"
      ((FAILED++))
    else
      CONTENT=$(echo "$BODY" | grep -o '"content":"[^"]*"' | head -1 | cut -d'"' -f4)
      echo "✅ Yanıt: $CONTENT (${DURATION}ms)"
      ((SUCCESS++))
    fi
  elif [ "$HTTP_CODE" = "429" ]; then
    echo "🚫 429 Rate Limited! (${DURATION}ms)"
    ((RATE_LIMITED++))
  elif [ "$HTTP_CODE" = "503" ]; then
    echo "⏳ 503 Kuyruk dolu/timeout (${DURATION}ms)"
    ((FAILED++))
  else
    echo "❌ HTTP $HTTP_CODE (${DURATION}ms)"
    ((FAILED++))
  fi
done

echo ""
echo "═══════════════ SONUÇLAR ═══════════════"
echo "  ✅ Başarılı:     $SUCCESS / $TOTAL_REQUESTS"
echo "  🚫 Rate Limited: $RATE_LIMITED"
echo "  ❌ Başarısız:    $FAILED"
echo ""

# Proxy istatistiklerini göster
echo "═══════════════ PROXY STATS ═══════════════"
curl -s "$API_URL/proxy/stats" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "(Proxy stats erişilemedi)"
echo ""
