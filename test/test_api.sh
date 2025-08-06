#!/bin/bash

# Test script for VM IP Change API using curl

# Configuration
BASE_URL="http://localhost:7071"  # Change this for production
FUNCTION_KEY=""  # Add function key for production
CURRENT_IP="20.123.45.67"  # Change this to actual IP

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Testing VM IP Change API${NC}"
echo "Base URL: $BASE_URL"
echo "Current IP: $CURRENT_IP"
echo "Function Key: ${FUNCTION_KEY:-'not provided'}"
echo "----------------------------------------"

# Test health endpoint
echo -e "\n${YELLOW}Testing health endpoint...${NC}"
if [ -n "$FUNCTION_KEY" ]; then
    HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/health?code=$FUNCTION_KEY")
else
    HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/api/health")
fi

HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$HEALTH_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✅ Health check passed${NC}"
    echo "Response: $RESPONSE_BODY"
else
    echo -e "${RED}❌ Health check failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $RESPONSE_BODY"
fi

# Test IP change endpoint
echo -e "\n${YELLOW}Testing IP change endpoint...${NC}"
REQUEST_BODY='{"current_ip":"'$CURRENT_IP'"}'

if [ -n "$FUNCTION_KEY" ]; then
    CHANGE_RESPONSE=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$REQUEST_BODY" \
        "$BASE_URL/api/change-vm-ip?code=$FUNCTION_KEY")
else
    CHANGE_RESPONSE=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$REQUEST_BODY" \
        "$BASE_URL/api/change-vm-ip")
fi

HTTP_CODE=$(echo "$CHANGE_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$CHANGE_RESPONSE" | head -n -1)

echo "Request: $REQUEST_BODY"
echo "HTTP Status: $HTTP_CODE"

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✅ IP change request successful${NC}"
    echo "Response: $RESPONSE_BODY" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
elif [ "$HTTP_CODE" -eq 404 ]; then
    echo -e "${YELLOW}⚠️  VM not found or access denied${NC}"
    echo "Response: $RESPONSE_BODY" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
else
    echo -e "${RED}❌ IP change request failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $RESPONSE_BODY" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
fi

echo -e "\n${GREEN}Test completed!${NC}"
