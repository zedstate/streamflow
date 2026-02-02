#!/bin/bash
echo "TESTING API ENDPOINTS"
# Get Token
TOKEN=$(curl -s -X POST http://localhost:9191/api/accounts/token/ -d '{"username":"admin", "password":"password"}' -H "Content-Type: application/json" | jq -r .access)

# Channels
# echo "CHANNELS:"
# curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:9191/api/channels/channels/?page_size=1" | jq .

# Current Programs
echo "CURRENT PROGRAMS:"
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:9191/api/epg/current-programs/?page_size=1" | jq .
