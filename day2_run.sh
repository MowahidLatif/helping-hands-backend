set -euo pipefail
BASE=http://127.0.0.1:5050
API_HOST=helpinghands.local:5050
PUB1=church.helpinghands.local:5050
PUB2=mosque.helpinghands.local:5050
TS=$(date +%s)
EMAIL="founder+$TS@example.com"
PASS="pw$TS!"
REG=$(curl -s -H "Host: $API_HOST" -H "Content-Type: application/json" -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"name\":\"Founder $TS\"}" "$BASE/api/auth/register")
LOGIN=$(curl -s -H "Host: $API_HOST" -H "Content-Type: application/json" -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" "$BASE/api/auth/login")
ACCESS=$(echo "$LOGIN" | jq -r .access_token)

create_org(){ curl -s -X POST -H "Host: $API_HOST" -H "Authorization: Bearer $ACCESS" -H "Content-Type: application/json" -d "{\"name\":\"$1\",\"subdomain\":\"$2\"}" "$BASE/api/orgs"; }
get_org_by_sub(){ curl -s -H "Host: $API_HOST" -H "Authorization: Bearer $ACCESS" "$BASE/api/orgs" | jq -c ".orgs[] | select(.subdomain==\"$1\")"; }
ensure_org(){ local NAME="$1" SUB="$2"; local R; R=$(create_org "$NAME" "$SUB" || true); if echo "$R" | jq -e .id >/dev/null 2>&1; then echo "$R"; else get_org_by_sub "$SUB"; fi; }

ORG1=$(ensure_org "Local Church" "church")
ORG1_ID=$(echo "$ORG1" | jq -r .id)
ORG2=$(ensure_org "City Mosque" "mosque")
ORG2_ID=$(echo "$ORG2" | jq -r .id)

create_campaign(){ curl -s -X POST -H "Host: $API_HOST" -H "Authorization: Bearer $ACCESS" -H "Content-Type: application/json" -d "{\"org_id\":\"$1\",\"title\":\"$2\"}" "$BASE/api/campaigns/"; }

C1=$(create_campaign "$ORG1_ID" "Food Drive 2025")
C2=$(create_campaign "$ORG2_ID" "Winter Relief 2025")
SLUG1=$(echo "$C1" | jq -r .slug)
SLUG2=$(echo "$C2" | jq -r .slug)

curl -s -H "Host: $PUB1" "$BASE/" | jq .
curl -s -H "Host: $PUB1" "$BASE/$SLUG1" | jq .
curl -s -H "Host: $PUB2" "$BASE/" | jq .
curl -s -H "Host: $PUB2" "$BASE/$SLUG2" | jq .
