#!/bin/bash
# Test script for Bento multi-agent flow via Agentverse
# Run: chmod +x test-agentverse-flow.sh && ./test-agentverse-flow.sh

BASE_URL="http://localhost:3000"
PASS=0
FAIL=0

echo "=============================================="
echo "🍱 BENTO AGENTVERSE MULTI-AGENT FLOW TEST"
echo "=============================================="
echo "Testing actual Agentverse agent calls..."
echo ""

# Helper function to check test results
check_result() {
    local test_name="$1"
    local condition="$2"
    local result="$3"
    
    if [ "$condition" = "true" ]; then
        echo "✅ PASS: $test_name"
        ((PASS++))
    else
        echo "❌ FAIL: $test_name"
        echo "   Result: $result"
        ((FAIL++))
    fi
}

# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: Simple eligibility check (US Citizen)
# Expected flow: Frontend → /api/intake → /api/chat → Agentverse EligibilityAgent
# ══════════════════════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 TEST 1: Simple eligibility - US Citizen, pregnant"
echo "   Expected: Bento → EligibilityAgent"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RESULT1=$(curl -s -X POST "$BASE_URL/api/intake" \
  -H "Content-Type: application/json" \
  -d '{
    "state": "California",
    "household_size": 3,
    "member_ages": ["26-40", "26-40", "1-4"],
    "health_flags": ["Currently pregnant"],
    "current_benefits": [],
    "income_range": 2000,
    "housing": "1200",
    "employment": "Working part-time (under 35 hours/week)",
    "immigration": "U.S. citizen or U.S. national"
  }')

# Check agents_called includes eligibility
AGENTS1=$(echo "$RESULT1" | jq -r '.agents_called // []')
HAS_BENTO=$(echo "$AGENTS1" | jq 'contains(["bento"])')
HAS_ELIGIBILITY=$(echo "$AGENTS1" | jq 'contains(["eligibility"])')
HAS_REPLY=$(echo "$RESULT1" | jq 'has("reply")')

echo "   Agents called: $(echo "$AGENTS1" | jq -r 'join(" → ")')"
check_result "Bento agent called" "$HAS_BENTO" "$AGENTS1"
check_result "Eligibility agent called" "$HAS_ELIGIBILITY" "$AGENTS1"
check_result "Got reply from agent" "$HAS_REPLY" "$(echo "$RESULT1" | jq -r '.reply[:80] // "no reply"')..."
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: Complex case (DACA recipient)
# Expected flow: Bento → EligibilityAgent → NavigatorAgent
# ══════════════════════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 TEST 2: Complex case - DACA recipient"
echo "   Expected: Bento → EligibilityAgent → NavigatorAgent"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RESULT2=$(curl -s -X POST "$BASE_URL/api/intake" \
  -H "Content-Type: application/json" \
  -d '{
    "state": "California",
    "household_size": 2,
    "member_ages": ["26-40", "1-4"],
    "health_flags": [],
    "current_benefits": [],
    "income_range": 1500,
    "housing": "900",
    "employment": "Working full-time (35+ hours/week)",
    "immigration": "DACA (Deferred Action for Childhood Arrivals)"
  }')

AGENTS2=$(echo "$RESULT2" | jq -r '.agents_called // []')
HAS_NAVIGATOR=$(echo "$AGENTS2" | jq 'contains(["navigator"])')
HAS_NAV_GUIDANCE=$(echo "$RESULT2" | jq 'has("navigator_guidance") and .navigator_guidance != null')

echo "   Agents called: $(echo "$AGENTS2" | jq -r 'join(" → ")')"
check_result "Navigator agent called for DACA" "$HAS_NAVIGATOR" "$AGENTS2"
check_result "Navigator guidance provided" "$HAS_NAV_GUIDANCE" "$(echo "$RESULT2" | jq -r '.navigator_guidance[:80] // "none"')"
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: Apply for SNAP
# Expected flow: Bento → ApplicationAgent → PolicyWatcherAgent
# ══════════════════════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 TEST 3: Apply for SNAP"
echo "   Expected: Bento → ApplicationAgent → PolicyWatcherAgent"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RESULT3=$(curl -s -X POST "$BASE_URL/api/apply" \
  -H "Content-Type: application/json" \
  -d '{
    "benefit_id": "SNAP",
    "profile": {
      "state": "California",
      "household_size": 3,
      "monthly_income": 2000,
      "is_pregnant": true,
      "has_child_under_5": true,
      "immigration_status": "citizen"
    }
  }')

AGENTS3=$(echo "$RESULT3" | jq -r '.agents_called // []')
HAS_APPLICATION=$(echo "$AGENTS3" | jq 'contains(["application"])')
HAS_POLICY=$(echo "$AGENTS3" | jq 'contains(["policy_watcher"])')
HAS_APP_GUIDE=$(echo "$RESULT3" | jq 'has("application_guide") and .application_guide != null')
HAS_POLICY_ALERTS=$(echo "$RESULT3" | jq 'has("policy_alerts") and .policy_alerts != null')

echo "   Agents called: $(echo "$AGENTS3" | jq -r 'join(" → ")')"
check_result "Application agent called" "$HAS_APPLICATION" "$AGENTS3"
check_result "PolicyWatcher agent called" "$HAS_POLICY" "$AGENTS3"
check_result "Application guide provided" "$HAS_APP_GUIDE" "$(echo "$RESULT3" | jq -r '.application_guide[:80] // "none"')"
check_result "Policy alerts provided" "$HAS_POLICY_ALERTS" "$(echo "$RESULT3" | jq -r '.policy_alerts[:80] // "none"')"
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: General chat (Bento only)
# ══════════════════════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 TEST 4: General chat"
echo "   Expected: Bento only"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RESULT4=$(curl -s -X POST "$BASE_URL/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is SNAP and how does it help families?"}')

AGENTS4=$(echo "$RESULT4" | jq -r '.agents_called // []')
AGENT_COUNT=$(echo "$AGENTS4" | jq 'length')
HAS_REPLY4=$(echo "$RESULT4" | jq 'has("reply") and (.reply | length) > 50')

echo "   Agents called: $(echo "$AGENTS4" | jq -r 'join(" → ")')"
echo "   Reply preview: $(echo "$RESULT4" | jq -r '.reply[:100] // "no reply"')..."
check_result "Bento responded" "$HAS_REPLY4" "$(echo "$RESULT4" | jq -r '.reply[:50] // "none"')"
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: Policy check for Medicaid
# Expected flow: Bento → PolicyWatcherAgent
# ══════════════════════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 TEST 5: Policy check for Medicaid"
echo "   Expected: Bento → PolicyWatcherAgent"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RESULT5=$(curl -s -X POST "$BASE_URL/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"intent": "policy_check", "benefit_id": "Medicaid"}')

AGENTS5=$(echo "$RESULT5" | jq -r '.agents_called // []')
HAS_POLICY5=$(echo "$AGENTS5" | jq 'contains(["policy_watcher"])')
HAS_REPLY5=$(echo "$RESULT5" | jq 'has("reply") and (.reply | length) > 20')

echo "   Agents called: $(echo "$AGENTS5" | jq -r 'join(" → ")')"
check_result "PolicyWatcher agent called" "$HAS_POLICY5" "$AGENTS5"
check_result "Policy info provided" "$HAS_REPLY5" "$(echo "$RESULT5" | jq -r '.reply[:80] // "none"')"
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: Undocumented immigrant (complex case)
# Expected: Should still get WIC guidance (no immigration check)
# ══════════════════════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 TEST 6: Undocumented immigrant with child"
echo "   Expected: Navigator called, WIC should be available"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RESULT6=$(curl -s -X POST "$BASE_URL/api/intake" \
  -H "Content-Type: application/json" \
  -d '{
    "state": "Texas",
    "household_size": 3,
    "member_ages": ["26-40", "26-40", "1-4"],
    "health_flags": ["Currently pregnant"],
    "current_benefits": [],
    "income_range": 1800,
    "housing": "800",
    "employment": "Working full-time (35+ hours/week)",
    "immigration": "Undocumented / No status"
  }')

AGENTS6=$(echo "$RESULT6" | jq -r '.agents_called // []')
HAS_NAVIGATOR6=$(echo "$AGENTS6" | jq 'contains(["navigator"])')
REPLY6=$(echo "$RESULT6" | jq -r '.reply // ""')
# Check if WIC is mentioned as available (since it doesn't check immigration)
MENTIONS_WIC=$(echo "$REPLY6" | grep -qi "wic" && echo "true" || echo "false")

echo "   Agents called: $(echo "$AGENTS6" | jq -r 'join(" → ")')"
check_result "Navigator called for undocumented" "$HAS_NAVIGATOR6" "$AGENTS6"
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# TEST 7: Direct eligibility API call
# ══════════════════════════════════════════════════════════════════════════════
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 TEST 7: Direct eligibility API"
echo "   Expected: Structured eligibility response"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RESULT7=$(curl -s -X POST "$BASE_URL/api/eligibility" \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "state": "NY",
      "household_size": 4,
      "monthly_income": 3000,
      "immigration_status": "citizen",
      "has_children": true,
      "has_child_under_5": true,
      "is_pregnant": false
    }
  }')

HAS_ELIGIBILITY7=$(echo "$RESULT7" | jq 'has("eligibility") or has("reply")')
echo "   Response keys: $(echo "$RESULT7" | jq -r 'keys | join(", ")')"
check_result "Eligibility response received" "$HAS_ELIGIBILITY7" "$(echo "$RESULT7" | jq -r '. | keys')"
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
echo "=============================================="
echo "📊 TEST SUMMARY"
echo "=============================================="
echo "✅ Passed: $PASS"
echo "❌ Failed: $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "🎉 ALL TESTS PASSED!"
    echo ""
    echo "Your Agentverse multi-agent flow is working:"
    echo "  • Bento orchestrator routes requests correctly"
    echo "  • EligibilityAgent analyzes profiles"
    echo "  • NavigatorAgent handles complex cases (DACA, undocumented)"
    echo "  • ApplicationAgent provides application guidance"
    echo "  • PolicyWatcherAgent surfaces policy updates"
    exit 0
else
    echo "⚠️  Some tests failed. Check the output above."
    echo ""
    echo "Common issues:"
    echo "  • Agentverse agents not deployed or not responding"
    echo "  • ASI1_API_KEY not set or invalid"
    echo "  • Agent addresses incorrect in /api/chat/route.ts"
    exit 1
fi
