#!/usr/bin/env bash
# Smoke test: call EVERY route of the deployed Sumaat API with curl and print PASS/FAIL.
#
# Usage (from the project folder, after a deploy):
#   SUMAAT_PASSWORD='...' ./scripts/smoke_test.sh            # demo password used by scripts/seed.py
#   SUMAAT_PASSWORD='...' RESTAURANT=qaisariya ./scripts/smoke_test.sh
#   SUMAAT_PASSWORD='...' VIA=cloudfront ./scripts/smoke_test.sh  # same tests through https://<site>/api
#
# Safe to re-run. It leaves realistic data and never duplicates it:
#   - menu item "Lamb Mandi" is created once, later runs edit it (and leave it available)
#   - cashier "Yousef Al-Mulla" is created once, later runs reuse him (left active, password = SUMAAT_PASSWORD)
#   - orders are real history: each run adds a few, all finished (served / cancelled / rejected)
#   - the restaurant is left open (resumed) with its hours unchanged
# Order tests are skipped if the restaurant is closed right now (Riyadh time).
#
# AI chat (always through CloudFront /agent/chat): the free checks (visitor, ID token, owner, empty message, quota
# route) use no AI and no daily messages. The real AI reply is opt-in, because it uses 1 of omar's 10 messages today:
#   SUMAAT_PASSWORD='...' CHAT=1 ./scripts/smoke_test.sh
# Needs: curl, jq, uv (for scripts/get_token.py), outputs.json from `cdk deploy --outputs-file outputs.json`.

set -u
cd "$(dirname "$0")/.."

: "${SUMAAT_PASSWORD:?Set SUMAAT_PASSWORD to the demo password}"
RESTAURANT="${RESTAURANT:-nakhla}"
if [ "${VIA:-api}" = cloudfront ]; then
  API="$(jq -r '.SumaatWeb.SiteUrl' outputs.json)/api"
else
  API="$(jq -r '.SumaatApi.ApiUrl' outputs.json)"
fi
API="${API%/}"
LAT=25.3797
LNG=49.5867

PASS=0
FAIL=0
SKIP=0
BODY=/tmp/sumaat_smoke_body.$$
trap 'rm -f "$BODY"' EXIT

green() { printf '\033[32m%s\033[0m' "$1"; }
red() { printf '\033[31m%s\033[0m' "$1"; }
section() { printf '\n== %s\n' "$1"; }

# req METHOD PATH [TOKEN] [JSON]  -> prints the HTTP status, body saved in $BODY
req() {
  local method="$1" path="$2" token="${3:-}" data="${4:-}"
  local args=(-s -o "$BODY" -w '%{http_code}' -X "$method" "$API$path" -H 'Content-Type: application/json')
  [ -n "$token" ] && args+=(-H "Authorization: $token")
  [ -n "$data" ] && args+=(-d "$data")
  curl "${args[@]}"
}

# check "name" EXPECTED METHOD PATH [TOKEN] [JSON]
check() {
  local name="$1" want="$2"
  shift 2
  local got
  got="$(req "$@")"
  if [ "$got" = "$want" ]; then
    PASS=$((PASS + 1))
    printf '%s  %-58s %s\n' "$(green PASS)" "$name" "$got"
  else
    FAIL=$((FAIL + 1))
    printf '%s  %-58s %s (want %s)  %s\n' "$(red FAIL)" "$name" "$got" "$want" "$(head -c 160 "$BODY")"
  fi
}

# expect "name" ACTUAL EXPECTED   (for values read from the last response)
expect() {
  if [ "$2" = "$3" ]; then
    PASS=$((PASS + 1))
    printf '%s  %-58s %s\n' "$(green PASS)" "$1" "$2"
  else
    FAIL=$((FAIL + 1))
    printf '%s  %-58s %s (want %s)\n' "$(red FAIL)" "$1" "$2" "$3"
  fi
}

skip() {
  SKIP=$((SKIP + 1))
  printf 'SKIP  %s\n' "$1"
}

field() { jq -r "$1" "$BODY"; }

token() { SUMAAT_PASSWORD="$SUMAAT_PASSWORD" uv run --quiet python scripts/get_token.py "$1" 2>/dev/null; }
atoken() { SUMAAT_PASSWORD="$SUMAAT_PASSWORD" uv run --quiet python scripts/get_token.py --access "$1" 2>/dev/null; }

echo "Sumaat smoke test -> $API (restaurant: $RESTAURANT)"

# --- logins ---------------------------------------------------------------------
OWNER="$(token "owner.$RESTAURANT@example.com")"
CASHIER="$(token "cashier.$RESTAURANT@example.com")"
SARA="$(token sara@example.com)"
OMAR="$(token omar@example.com)"
OTHER_OWNER="$(token "owner.$([ "$RESTAURANT" = qaisariya ] && echo mubarraz || echo qaisariya)@example.com")"
for t in OWNER CASHIER SARA OMAR OTHER_OWNER; do
  if [ -z "${!t}" ]; then
    echo "Could not log in as $t. Check SUMAAT_PASSWORD (and that the seed ran)."
    exit 1
  fi
done

# Restaurant id: the owner's token carries it.
RID="$(printf '%s' "$OWNER" | cut -d. -f2 | tr '_-' '/+' | base64 -D 2>/dev/null | jq -r '."custom:restaurantId"' 2>/dev/null)"
if [ -z "$RID" ] || [ "$RID" = null ]; then
  # base64 padding can trip macOS base64; fall back to Python
  RID="$(printf '%s' "$OWNER" | uv run --quiet python -c 'import sys,json,base64;p=sys.stdin.read().split(".")[1];print(json.loads(base64.urlsafe_b64decode(p+"="*(-len(p)%4)))["custom:restaurantId"])')"
fi

# --- public ---------------------------------------------------------------------
section "Public routes (no login)"
check "GET /health" 200 GET /health
check "GET /categories" 200 GET /categories
expect "categories include Mains" "$(field '.categories | index("Mains") != null')" true
check "GET /restaurants near me (4 km)" 200 GET "/restaurants?lat=$LAT&lng=$LNG&radiusKm=4"
expect "near me finds 3 demo restaurants" "$(field '[.[] | select(.name | test("Nakhla|Qaisariya|Mubarraz"))] | length')" 3
check "GET /restaurants radius 4.5 -> 422" 422 GET "/restaurants?lat=$LAT&lng=$LNG&radiusKm=4.5"
check "GET /restaurants radius 4.2 -> 422 (cap is 4 km)" 422 GET "/restaurants?lat=$LAT&lng=$LNG&radiusKm=4.2"
check "GET /restaurants missing lat -> 422" 422 GET "/restaurants?lng=$LNG"
check "GET /restaurants/{id}" 200 GET "/restaurants/$RID"
expect "restaurant has openNow / isPaused" "$(field 'has("openNow") and has("isPaused")')" true
expect "restaurant hides ownerSub" "$(field 'has("ownerSub")')" false
OPEN_NOW="$(field '.openNow')"
HOURS="$(field '.hours')"
check "GET /restaurants/unknown -> 404" 404 GET /restaurants/not-a-real-id
check "GET /docs is not public -> 401" 401 GET /docs

section "Login gate (API Gateway)"
check "POST /restaurants without token -> 401" 401 POST /restaurants "" '{}'
check "POST /orders with fake token -> 401" 401 POST /orders "not-a-token" '{}'
PREFLIGHT="$(curl -s -o /dev/null -D - -X OPTIONS "$API/restaurants" -H 'Origin: http://localhost:5173' \
  -H 'Access-Control-Request-Method: POST' | tr -d '\r' | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}')"
expect "CORS preflight allows localhost:5173" "$PREFLIGHT" "http://localhost:5173"

# --- restaurants ----------------------------------------------------------------
section "Restaurants (owner)"
NEW_R='{"name":"Second Branch","nameAr":"فرع ثاني","city":"Al-Hofuf","district":"Al-Kut","lat":25.38,"lng":49.58,"hours":"10:00-22:00"}'
check "POST /restaurants second one -> 409" 409 POST /restaurants "$OWNER" "$NEW_R"
check "POST /restaurants as customer -> 403" 403 POST /restaurants "$SARA" "$NEW_R"
check "POST /restaurants as cashier -> 403" 403 POST /restaurants "$CASHIER" "$NEW_R"
check "PATCH /restaurants/{id} hours (same value)" 200 PATCH "/restaurants/$RID" "$OWNER" "{\"hours\":\"$HOURS\"}"
check "PATCH old isOpen field -> 422" 422 PATCH "/restaurants/$RID" "$OWNER" '{"isOpen":false}'
check "PATCH empty body -> 422" 422 PATCH "/restaurants/$RID" "$OWNER" '{}'
check "PATCH by another owner -> 403" 403 PATCH "/restaurants/$RID" "$OTHER_OWNER" '{"name":"Hacked"}'
check "PATCH by cashier -> 403" 403 PATCH "/restaurants/$RID" "$CASHIER" '{"name":"Hacked"}'
check "PATCH unknown restaurant -> 404" 404 PATCH /restaurants/not-a-real-id "$OWNER" '{"name":"x"}'

section "Pause / resume"
check "owner pauses" 200 POST "/restaurants/$RID/pause" "$OWNER"
expect "paused -> openNow false" "$(field '.openNow')" false
check "owner resumes" 200 POST "/restaurants/$RID/resume" "$OWNER"
check "cashier pauses" 200 POST "/restaurants/$RID/pause" "$CASHIER"
check "cashier resumes" 200 POST "/restaurants/$RID/resume" "$CASHIER"
expect "resumed -> isPaused false" "$(field '.isPaused')" false
check "customer pause -> 403" 403 POST "/restaurants/$RID/pause" "$SARA"
check "another owner pause -> 403" 403 POST "/restaurants/$RID/pause" "$OTHER_OWNER"

# --- menu -----------------------------------------------------------------------
section "Menu (owner)"
DISH='{"name":"Lamb Mandi","nameAr":"مندي لحم","category":"Mains","priceHalalas":4800,"calories":1050,"dietTags":["high_protein","gluten_free","dairy_free"]}'
req GET "/restaurants/$RID" >/dev/null
MANDI="$(field '[.menu[] | select(.name == "Lamb Mandi")][0].id // empty')"
if [ -z "$MANDI" ]; then
  check "POST menu item Lamb Mandi (first run)" 201 POST "/restaurants/$RID/menu" "$OWNER" "$DISH"
  MANDI="$(field '.id')"
else
  skip "POST menu item: Lamb Mandi already exists (not duplicated); route tested on its first run"
fi
check "POST menu item price 15.5 -> 422" 422 POST "/restaurants/$RID/menu" "$OWNER" '{"name":"x","nameAr":"x","category":"Mains","priceHalalas":15.5}'
check "POST menu item unknown category -> 422" 422 POST "/restaurants/$RID/menu" "$OWNER" '{"name":"x","nameAr":"x","category":"Tacos","priceHalalas":1500}'
check "POST menu item extra field -> 422" 422 POST "/restaurants/$RID/menu" "$OWNER" '{"name":"x","nameAr":"x","category":"Mains","priceHalalas":1500,"restaurantId":"x"}'
check "POST menu item as other owner -> 403" 403 POST "/restaurants/$RID/menu" "$OTHER_OWNER" "$DISH"
check "POST menu item as cashier -> 403" 403 POST "/restaurants/$RID/menu" "$CASHIER" "$DISH"
check "PATCH menu item price" 200 PATCH "/restaurants/$RID/menu/$MANDI" "$OWNER" '{"priceHalalas":4800}'
check "PATCH menu item hide" 200 PATCH "/restaurants/$RID/menu/$MANDI" "$OWNER" '{"isAvailable":false}'
check "PATCH menu item show again" 200 PATCH "/restaurants/$RID/menu/$MANDI" "$OWNER" '{"isAvailable":true}'
check "PATCH unknown menu item -> 404" 404 PATCH "/restaurants/$RID/menu/not-a-real-id" "$OWNER" '{"priceHalalas":100}'
check "PATCH menu item by other owner -> 403" 403 PATCH "/restaurants/$RID/menu/$MANDI" "$OTHER_OWNER" '{"priceHalalas":1}'

# --- cashiers -------------------------------------------------------------------
section "Cashiers (owner)"
NEWC_EMAIL="yousef.$RESTAURANT@example.com"
NEWC="{\"name\":\"Yousef Al-Mulla\",\"email\":\"$NEWC_EMAIL\",\"phone\":\"+966500000260\",\"password\":\"$SUMAAT_PASSWORD\"}"
check "GET /restaurants/{id}/cashiers" 200 GET "/restaurants/$RID/cashiers" "$OWNER"
YOUSEF="$(field '[.[] | select(.email == "'"$NEWC_EMAIL"'")][0].sub // empty')"
if [ -z "$YOUSEF" ]; then
  check "POST cashier Yousef (first run)" 201 POST "/restaurants/$RID/cashiers" "$OWNER" "$NEWC"
  YOUSEF="$(field '.sub')"
else
  check "POST cashier Yousef again -> 409 (no duplicate)" 409 POST "/restaurants/$RID/cashiers" "$OWNER" "$NEWC"
fi
check "POST cashier weak password -> 422" 422 POST "/restaurants/$RID/cashiers" "$OWNER" '{"name":"X","email":"weak.pw@example.com","phone":"+966500000261","password":"weak"}'
check "POST cashier bad phone -> 422" 422 POST "/restaurants/$RID/cashiers" "$OWNER" '{"name":"X","email":"bad.phone@example.com","phone":"0500000261","password":"Good#2026"}'
check "POST cashier non-Saudi phone -> 422" 422 POST "/restaurants/$RID/cashiers" "$OWNER" '{"name":"X","email":"us.phone@example.com","phone":"+14155550100","password":"Good#2026"}'
check "POST cashier name with digits -> 422" 422 POST "/restaurants/$RID/cashiers" "$OWNER" '{"name":"Ali2","email":"bad.name@example.com","phone":"+966500000261","password":"Good#2026"}'
check "POST cashier with customer's email -> 409" 409 POST "/restaurants/$RID/cashiers" "$OWNER" '{"name":"X","email":"sara@example.com","phone":"+966500000261","password":"Good#2026"}'
check "GET cashiers as cashier -> 403" 403 GET "/restaurants/$RID/cashiers" "$CASHIER"
check "GET cashiers as other owner -> 403" 403 GET "/restaurants/$RID/cashiers" "$OTHER_OWNER"
check "reset Yousef's password" 204 POST "/restaurants/$RID/cashiers/$YOUSEF/password" "$OWNER" "{\"password\":\"$SUMAAT_PASSWORD\"}"
YOUSEF_T="$(token "$NEWC_EMAIL")"
check "Yousef (new token) can pause" 200 POST "/restaurants/$RID/pause" "$YOUSEF_T"
check "Yousef resumes" 200 POST "/restaurants/$RID/resume" "$YOUSEF_T"
check "owner disables Yousef" 200 POST "/restaurants/$RID/cashiers/$YOUSEF/disable" "$OWNER"
check "Yousef's same token blocked at once -> 403" 403 POST "/restaurants/$RID/pause" "$YOUSEF_T"
check "owner enables Yousef again" 200 POST "/restaurants/$RID/cashiers/$YOUSEF/enable" "$OWNER"
expect "Yousef active" "$(field '.status')" active
check "disable unknown cashier -> 404" 404 POST "/restaurants/$RID/cashiers/not-a-real-sub/disable" "$OWNER"
check "other owner disables Yousef -> 403" 403 POST "/restaurants/$RID/cashiers/$YOUSEF/disable" "$OTHER_OWNER"

# --- orders ---------------------------------------------------------------------
section "Orders"
check "GET /orders/mine (Sara)" 200 GET /orders/mine "$SARA"
check "GET /orders/mine as owner -> 403" 403 GET /orders/mine "$OWNER"
check "GET today's orders (cashier)" 200 GET "/restaurants/$RID/orders" "$CASHIER"
check "GET orders by date + status (owner)" 200 GET "/restaurants/$RID/orders?date=2026-11-11&status=SERVED" "$OWNER"
check "GET today's orders as customer -> 403" 403 GET "/restaurants/$RID/orders" "$SARA"
check "GET orders bad status -> 422" 422 GET "/restaurants/$RID/orders?status=NOPE" "$OWNER"
check "GET /orders/unknown -> 404" 404 GET /orders/not-a-real-id "$SARA"

req GET "/restaurants/$RID" >/dev/null
I1="$(field '[.menu[] | select(.isAvailable)][0].id')"
I2="$(field '[.menu[] | select(.isAvailable)][1].id')"
ORDER_A="{\"restaurantId\":\"$RID\",\"items\":[{\"itemId\":\"$I1\",\"qty\":2},{\"itemId\":\"$I2\",\"qty\":1}],\"note\":\"Extra lemon please\"}"
ORDER_B="{\"restaurantId\":\"$RID\",\"items\":[{\"itemId\":\"$I1\",\"qty\":1}],\"note\":\"Pickup in 20 minutes\"}"

check "POST order as owner -> 403" 403 POST /orders "$OWNER" "$ORDER_A"
check "POST order as cashier -> 403" 403 POST /orders "$CASHIER" "$ORDER_A"
check "POST order with a price field -> 422" 422 POST /orders "$SARA" "{\"restaurantId\":\"$RID\",\"items\":[{\"itemId\":\"$I1\",\"qty\":1,\"priceHalalas\":1}]}"
check "POST order qty 0 -> 422" 422 POST /orders "$SARA" "{\"restaurantId\":\"$RID\",\"items\":[{\"itemId\":\"$I1\",\"qty\":0}]}"
check "POST order unknown restaurant -> 404" 404 POST /orders "$SARA" "{\"restaurantId\":\"nope\",\"items\":[{\"itemId\":\"$I1\",\"qty\":1}]}"

# Leftover open orders from manual testing would block "one open order per restaurant": finish them first.
# Placed -> the customer cancels it. Accepted/Ready -> the cashier takes it to Served.
cleanup_open_orders() {
  local who="$1" token="$2"
  req GET /orders/mine "$token" >/dev/null
  jq -r --arg rid "$RID" '.[] | select(.restaurantId == $rid and (.status == "PLACED" or .status == "ACCEPTED" or .status == "READY_FOR_PICKUP")) | "\(.id) \(.status) \(.orderNumber)"' "$BODY" |
    while read -r oid status num; do
      case "$status" in
        PLACED) req POST "/orders/$oid/cancel" "$token" >/dev/null ;;
        ACCEPTED) req POST "/orders/$oid/ready" "$CASHIER" >/dev/null; req POST "/orders/$oid/served" "$CASHIER" >/dev/null ;;
        READY_FOR_PICKUP) req POST "/orders/$oid/served" "$CASHIER" >/dev/null ;;
      esac
      printf '      cleaned up %s'"'"'s open order #%s (%s)\n' "$who" "$num" "$status"
    done
}
cleanup_open_orders Sara "$SARA"
cleanup_open_orders Omar "$OMAR"

if [ "$OPEN_NOW" != true ]; then
  skip "placing and handling orders: restaurant is closed now (hours $HOURS, Riyadh time)"
else
  # Sara: place -> 409 second -> cashier accept/ready/served
  check "Sara places an order" 201 POST /orders "$SARA" "$ORDER_A"
  O1="$(field '.id')"
  printf '      order #%s on %s, total %s halalas\n' "$(field '.orderNumber')" "$(field '.businessDate')" "$(field '.totalHalalas')"
  expect "email never returned" "$(field 'has("customerEmail")')" false
  check "Sara second order here -> 409" 409 POST /orders "$SARA" "$ORDER_B"
  check "Sara reads her order" 200 GET "/orders/$O1" "$SARA"
  check "Omar cannot read Sara's order -> 404" 404 GET "/orders/$O1" "$OMAR"
  check "other owner cannot read it -> 404" 404 GET "/orders/$O1" "$OTHER_OWNER"
  check "cashier reads it" 200 GET "/orders/$O1" "$CASHIER"
  expect "cashier sees customer phone" "$(field '.customerPhone')" "+966500000301"
  check "ready before accept -> 409" 409 POST "/orders/$O1/ready" "$CASHIER"
  check "customer accept -> 404" 404 POST "/orders/$O1/accept" "$SARA"
  check "cashier accepts" 200 POST "/orders/$O1/accept" "$CASHIER"
  check "Sara cancel after accept -> 409" 409 POST "/orders/$O1/cancel" "$SARA"
  check "cashier marks ready" 200 POST "/orders/$O1/ready" "$CASHIER"
  check "owner marks served" 200 POST "/orders/$O1/served" "$OWNER"
  expect "history has 4 steps" "$(field '.statusHistory | length')" 4
  check "accept after served -> 409" 409 POST "/orders/$O1/accept" "$CASHIER"
  check "Sara's list shows it" 200 GET /orders/mine "$SARA"
  expect "Sara's latest order is SERVED" "$(field '.[0].status')" SERVED

  # Sara orders again (lock released) and cancels
  check "Sara orders again after served" 201 POST /orders "$SARA" "$ORDER_B"
  O2="$(field '.id')"
  check "Sara cancels while PLACED" 200 POST "/orders/$O2/cancel" "$SARA"
  check "cashier accept cancelled -> 409" 409 POST "/orders/$O2/accept" "$CASHIER"

  # Omar orders, cashier rejects with a reason
  check "Omar places an order" 201 POST /orders "$OMAR" "$ORDER_B"
  O3="$(field '.id')"
  check "Sara cancels Omar's order -> 404" 404 POST "/orders/$O3/cancel" "$SARA"
  check "cashier rejects with reason" 200 POST "/orders/$O3/reject" "$CASHIER" '{"reason":"Kitchen is closing early today"}'
  expect "reason saved" "$(field '.statusHistory[-1].reason')" "Kitchen is closing early today"
  check "Omar cancel rejected order -> 409" 409 POST "/orders/$O3/cancel" "$OMAR"

  # Paused restaurant refuses new orders
  req POST "/restaurants/$RID/pause" "$CASHIER" >/dev/null
  check "order while paused -> 409" 409 POST /orders "$OMAR" "$ORDER_B"
  req POST "/restaurants/$RID/resume" "$CASHIER" >/dev/null
fi

# --- AI chat ----------------------------------------------------------------------
section "AI chat"
AGENT="$(jq -r '.SumaatWeb.SiteUrl' outputs.json)"
AGENT="${AGENT%/}/agent/chat"
OMAR_A="$(atoken omar@example.com)"
OWNER_A="$(atoken "owner.$RESTAURANT@example.com")"

# chat [BEARER_TOKEN] JSON -> prints "HTTP_STATUS SECONDS", the SSE stream saved in $BODY
chat() {
  local token="$1" data="$2"
  local args=(-sN --max-time 60 -o "$BODY" -w '%{http_code} %{time_total}' -X POST "$AGENT"
    -H 'Content-Type: application/json'
    -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: smoke-$(uuidgen | tr 'A-Z' 'a-z')" -d "$data")
  [ -n "$token" ] && args+=(-H "Authorization: Bearer $token")
  curl "${args[@]}"
}
# events -> one JSON event per line (the "data: " lines of the stream)
events() { sed -n 's/^data: //p' "$BODY"; }
HELLO='{"message":"hi","lang":"en"}'

expect "chat as visitor -> 401" "$(chat "" "$HELLO" | cut -d' ' -f1)" 401
expect "chat with ID token -> 401 (needs access token)" "$(chat "$OMAR" "$HELLO" | cut -d' ' -f1)" 401
expect "chat as owner -> 200" "$(chat "$OWNER_A" "$HELLO" | cut -d' ' -f1)" 200
expect "  ... error not_customer" "$(events | jq -r 'select(.type == "error") | .code' | head -1)" not_customer
chat "$OMAR_A" '{"message":"   ","lang":"en"}' >/dev/null
expect "chat empty message -> invalid_message" "$(events | jq -r 'select(.type == "error") | .code' | head -1)" invalid_message

check "GET /me/chat-quota (Omar)" 200 GET /me/chat-quota "$OMAR"
LEFT="$(field '.left')"
expect "chat daily limit is 10" "$(field '.limit')" 10
expect "chat messages left is 0-10" "$([ "$LEFT" -ge 0 ] 2>/dev/null && [ "$LEFT" -le 10 ] && echo yes || echo "no ($LEFT)")" yes
check "GET /me/chat-quota as owner -> 403" 403 GET /me/chat-quota "$OWNER"
check "GET /me/chat-quota without token -> 401" 401 GET /me/chat-quota

if [ "${CHAT:-0}" != 1 ]; then
  skip "AI reply: set CHAT=1 (uses 1 of omar's 10 daily messages)"
elif [ "$LEFT" = 0 ]; then
  skip "AI reply: omar has no chat messages left today"
else
  read -r CODE SECS < <(chat "$OMAR_A" "{\"message\":\"What desserts are near me?\",\"lat\":$LAT,\"lng\":$LNG,\"lang\":\"en\"}")
  expect "AI reply -> 200" "$CODE" 200
  expect "  ... first event: quota, one fewer left" "$(events | head -1 | jq -r '"\(.type) \(.left)"')" "quota $((LEFT - 1))"
  expect "  ... has text" "$(events | jq -r 'select(.type == "text") | .type' | head -1)" text
  expect "  ... not blocked, no error" "$(events | jq -r 'select(.type == "blocked" or .type == "error") | "\(.type) \(.code // "")"' | head -1)" ""
  expect "  ... ends with done" "$(events | tail -1 | jq -r '.type')" done
  printf '      reply in %.1f s: %s\n' "$SECS" "$(events | jq -rj 'select(.type == "text") | .delta' | tr '\n' ' ' | head -c 100)"
fi

# --- end state --------------------------------------------------------------------
req GET "/restaurants/$RID" >/dev/null
expect "restaurant left resumed" "$(field '.isPaused')" false
expect "Lamb Mandi left available" "$(field '[.menu[] | select(.name == "Lamb Mandi")][0].isAvailable')" true

printf '\n%s passed, %s failed, %s skipped\n' "$PASS" "$FAIL" "$SKIP"
[ "$FAIL" -eq 0 ]
