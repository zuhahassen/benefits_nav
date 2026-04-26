#!/bin/bash
# Test script for Bento multi-agent flow
# Run: chmod +x test-flow.sh && ./test-flow.sh

BASE_URL="http://localhost:3000"

echo "=============================================="
echo "🍱 BENTO MULTI-AGENT FLOW TEST"
echo "=============================================="
echo ""

# Test 1: Simple eligible case (US Citizen)
echo "📋 TEST 1: Simple case - US Citizen, low income, pregnant"
echo "Expected: Bento → EligibilityAgent"
echo "----------------------------------------------"
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

echo "Agents called: $(echo $RESULT1 | jq -r '.agents_called // ["unknown"] | join(" → ")')"
echo "Eligibility:"
echo "$RESULT1" | jq -r '.eligibility | to_entries[] | "  \(.key): \(.value.verdict)"'
echo ""

# Test 2: Complex case (DACA)
echo "📋 TEST 2: Complex case - DACA recipient"
echo "Expected: Bento → EligibilityAgent → NavigatorAgent"
echo "----------------------------------------------"
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

echo "Agents called: $(echo $RESULT2 | jq -r '.agents_called // ["unknown"] | join(" → ")')"
echo "Has navigator guidance: $(echo $RESULT2 | jq 'if .navigator_guidance then "YES ✓" else "NO" end')"
echo "Eligibility:"
echo "$RESULT2" | jq -r '.eligibility | to_entries[] | "  \(.key): \(.value.verdict)"'
echo ""

# Test 3: Apply for SNAP
echo "📋 TEST 3: Apply for SNAP"
echo "Expected: Bento → ApplicationAgent → PolicyWatcherAgent"
echo "----------------------------------------------"
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

echo "Agents called: $(echo $RESULT3 | jq -r '.agents_called // ["unknown"] | join(" → ")')"
echo "Has application guide: $(echo $RESULT3 | jq 'if .application_guide then "YES ✓" else "NO" end')"
echo "Has policy alerts: $(echo $RESULT3 | jq 'if .policy_alerts then "YES ✓" else "NO" end')"
echo ""

# Test 4: General chat
echo "📋 TEST 4: General chat"
echo "Expected: Bento only"
echo "----------------------------------------------"
RESULT4=$(curl -s -X POST "$BASE_URL/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is SNAP?"}')

echo "Agents called: $(echo $RESULT4 | jq -r '.agents_called // ["unknown"] | join(" → ")')"
echo "Reply preview: $(echo $RESULT4 | jq -r '.reply[:100]')..."
echo ""

# Test 5: Policy check
echo "📋 TEST 5: Policy check for Medicaid"
echo "Expected: Bento → PolicyWatcherAgent"
echo "----------------------------------------------"
RESULT5=$(curl -s -X POST "$BASE_URL/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"intent": "policy_check", "benefit_id": "Medicaid"}')

echo "Agents called: $(echo $RESULT5 | jq -r '.agents_called // ["unknown"] | join(" → ")')"
echo ""

echo "=============================================="
echo "✅ ALL TESTS COMPLETE"
echo "=============================================="
