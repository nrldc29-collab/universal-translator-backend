#!/bin/bash
# Test Anai Translator Backend
# Usage: ./test-backend.sh [http://localhost:8000]

BACKEND=${1:-http://localhost:8000}

echo "=== Testing Anai Translator Backend ==="
echo "Target: $BACKEND"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

test_endpoint() {
  local name=$1
  local url=$2
  local expected_code=${3:-200}
  
  echo -n "Testing $name... "
  response=$(curl -s -w "\n%{http_code}" "$url")
  http_code=$(echo "$response" | tail -n 1)
  body=$(echo "$response" | sed '$d')
  
  if [ "$http_code" = "$expected_code" ]; then
    echo -e "${GREEN}✓ ($http_code)${NC}"
    if [ ! -z "$body" ]; then
      echo "  Response: $(echo $body | head -c 100)..."
    fi
  else
    echo -e "${RED}✗ Expected $expected_code, got $http_code${NC}"
    return 1
  fi
}

# Test endpoints
test_endpoint "Health" "$BACKEND/health" 200
test_endpoint "Ready" "$BACKEND/ready" 200
test_endpoint "Languages" "$BACKEND/languages" 200
test_endpoint "Docs" "$BACKEND/docs" 200
test_endpoint "OpenAPI JSON" "$BACKEND/openapi.json" 200

echo ""
echo "=== Text Translation Test ==="
echo "Testing: 'Hello, how are you?' (English -> Spanish)"

curl -s -X POST "$BACKEND/translate/text" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, how are you?",
    "source_lang": "en",
    "target_lang": "es"
  }' | python3 -m json.tool

echo ""
echo "=== WebSocket Test ==="
echo "WebSocket endpoint should be at: ${BACKEND//http/ws}/ws/audio"
echo "Test with frontend: https://your-frontend.example.com"
echo ""

if command -v wscat &> /dev/null; then
  echo "wscat found. Testing WebSocket connection..."
  timeout 5 wscat -c "${BACKEND//http/ws}/ws/audio" || true
else
  echo "wscat not found. Install with: npm install -g wscat"
  echo "Then test: wscat -c ${BACKEND//http/ws}/ws/audio"
fi

echo ""
echo -e "${GREEN}=== Test Complete ===${NC}"
