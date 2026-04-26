"""
Knowledge Base for Benefits Navigator Agents
Fetches benefits data from API and provides semantic search via ASI-1 Mini
"""
import json
import os
from typing import Optional
from openai import OpenAI

# Benefits data cache
_benefits_cache: Optional[dict] = None

# API endpoint for benefits data (can be local or deployed)
BENEFITS_API_URL = os.getenv("BENEFITS_API_URL", "http://localhost:3000/api/benefits")

def get_benefits_data() -> dict:
    """
    Fetch benefits data from API or return cached version.
    Falls back to embedded data if API unavailable.
    """
    global _benefits_cache
    
    if _benefits_cache is not None:
        return _benefits_cache
    
    # Try to fetch from API
    try:
        import urllib.request
        with urllib.request.urlopen(BENEFITS_API_URL, timeout=5) as response:
            _benefits_cache = json.loads(response.read().decode())
            return _benefits_cache
    except Exception as e:
        print(f"[KnowledgeBase] API fetch failed: {e}, using embedded data")
    
    # Fallback: embedded data (updated 2025-04)
    _benefits_cache = {
        "fpl_annual_2025": {1: 15650, 2: 21150, 3: 26650, 4: 32150, 5: 37650, 6: 43150, 7: 48650, 8: 54150},
        "benefits": {
            "SNAP": {
                "name": "Supplemental Nutrition Assistance Program",
                "description": "Monthly food assistance loaded onto an EBT card",
                "gross_monthly_limits_2025": {1: 1640, 2: 2216, 3: 2792, 4: 3368, 5: 3944, 6: 4520, 7: 5096, 8: 5672},
                "eligible_statuses": ["citizen", "lpr_5yr", "refugee", "asylee", "humanitarian"],
                "ineligible_statuses": ["daca", "undocumented", "visa"],
                "apply_url": "https://www.benefits.gov/benefit/361",
                "docs_required": ["Photo ID", "Proof of address", "Pay stubs (last 30 days)", "SSN for all members", "Bank statements"],
                "processing_time": "30 days (7 days expedited)",
            },
            "Medicaid": {
                "name": "Medicaid",
                "description": "Free or low-cost health coverage",
                "gross_monthly_limits_2025": {1: 1732, 2: 2340, 3: 2948, 4: 3556, 5: 4164, 6: 4772, 7: 5380, 8: 5988},
                "fpl_pct_limit": 138,
                "eligible_statuses": ["citizen", "lpr_5yr", "refugee", "asylee", "humanitarian"],
                "ineligible_statuses": ["undocumented"],
                "daca_state_programs": ["CA", "NY", "IL", "WA", "OR", "CO", "NJ", "MA", "CT", "RI", "DC"],
                "apply_url": "https://www.healthcare.gov/medicaid-chip/getting-medicaid-chip/",
                "docs_required": ["Proof of identity", "Immigration docs", "Proof of residency", "Proof of income"],
                "processing_time": "45 days",
            },
            "TANF": {
                "name": "Temporary Assistance for Needy Families",
                "description": "Cash assistance for families with children",
                "fpl_pct_limit": 50,
                "requires_children": True,
                "eligible_statuses": ["citizen", "lpr_5yr", "refugee", "asylee"],
                "ineligible_statuses": ["daca", "undocumented", "lpr_under5yr", "visa"],
                "child_only_grants_available": True,
                "apply_url": "https://www.benefits.gov/benefit/613",
                "docs_required": ["Birth certificates for children", "Proof of identity", "Proof of income", "SSN for all"],
                "processing_time": "30-45 days",
            },
            "WIC": {
                "name": "Women, Infants, and Children",
                "description": "Nutrition program for pregnant/postpartum women and children under 5",
                "gross_monthly_limits_2025": {1: 2313, 2: 3127, 3: 3940, 4: 4754, 5: 5567, 6: 6381, 7: 7194, 8: 8008},
                "fpl_pct_limit": 185,
                "all_immigration_eligible": True,
                "requires_wic_category": True,
                "wic_categories": ["pregnant", "postpartum_6mo", "breastfeeding_12mo", "infant", "child_under_5"],
                "categorical_eligibility": ["SNAP", "Medicaid", "TANF"],
                "apply_url": "https://www.fns.usda.gov/wic/wic-how-apply",
                "docs_required": ["Proof of identity", "Proof of residency", "Proof of income or SNAP/Medicaid/TANF", "Proof of pregnancy/child age"],
                "processing_time": "Same day to 2 weeks",
            },
            "LIHEAP": {
                "name": "Low Income Home Energy Assistance Program",
                "description": "Help paying heating and cooling bills",
                "gross_monthly_limits_2025": {1: 1876, 2: 2535, 3: 3194, 4: 3853, 5: 4512, 6: 5171, 7: 5830, 8: 6489},
                "fpl_pct_limit": 150,
                "eligible_statuses": ["citizen", "lpr", "refugee", "asylee", "daca", "humanitarian"],
                "seasonal_program": True,
                "apply_url": "https://www.benefits.gov/benefit/623",
                "docs_required": ["Proof of identity", "Recent utility bills", "Proof of income", "SSN"],
                "processing_time": "2-4 weeks",
            },
        },
        "policy_updates": [
            {"date": "2025-03-15", "benefit": "SNAP", "title": "SNAP Income Limits Increased", "summary": "Gross income limits increased ~3.5%"},
            {"date": "2025-02-01", "benefit": "Medicaid", "title": "Medicaid Unwinding Continues", "summary": "Check your coverage status and renew if needed"},
        ],
    }
    return _benefits_cache


def get_benefit_info(benefit_name: str) -> dict:
    """Get info for a specific benefit."""
    data = get_benefits_data()
    return data.get("benefits", {}).get(benefit_name, {})


def get_income_limit(benefit_name: str, household_size: int) -> int:
    """Get the income limit for a benefit and household size."""
    benefit = get_benefit_info(benefit_name)
    limits = benefit.get("gross_monthly_limits_2025", {})
    size_key = str(min(household_size, 8))
    return limits.get(size_key, limits.get(int(size_key), 0))


def get_fpl(household_size: int) -> int:
    """Get Federal Poverty Level for household size."""
    data = get_benefits_data()
    fpl = data.get("fpl_annual_2025", {})
    size_key = str(min(household_size, 8))
    return fpl.get(size_key, fpl.get(int(size_key), 15650))


def check_immigration_eligible(benefit_name: str, immigration_status: str) -> tuple[bool, str]:
    """
    Check if immigration status is eligible for a benefit.
    Returns (is_eligible, reason)
    """
    benefit = get_benefit_info(benefit_name)
    
    # WIC doesn't check immigration
    if benefit.get("all_immigration_eligible"):
        return True, "This benefit does not check immigration status."
    
    eligible = benefit.get("eligible_statuses", [])
    ineligible = benefit.get("ineligible_statuses", [])
    
    if immigration_status in ineligible:
        # Check for state programs (Medicaid + DACA)
        if benefit_name == "Medicaid" and immigration_status == "daca":
            states = benefit.get("daca_state_programs", [])
            return False, f"DACA recipients may qualify in these states: {', '.join(states)}"
        return False, f"Immigration status '{immigration_status}' is not eligible for {benefit_name}."
    
    if immigration_status in eligible:
        return True, "Immigration status is eligible."
    
    return False, "Immigration status eligibility unclear — apply to find out."


def semantic_search(query: str, api_key: str, top_k: int = 3) -> list[dict]:
    """
    Use ASI-1 Mini to find relevant benefits info for a query.
    Returns list of relevant chunks with scores.
    """
    data = get_benefits_data()
    
    # Build searchable chunks
    chunks = []
    for benefit_name, benefit_info in data.get("benefits", {}).items():
        chunks.append({
            "type": "benefit",
            "name": benefit_name,
            "content": json.dumps(benefit_info),
            "text": f"{benefit_name}: {benefit_info.get('description', '')}. Eligible: {benefit_info.get('eligible_statuses', [])}. Docs needed: {benefit_info.get('docs_required', [])}"
        })
    
    for update in data.get("policy_updates", []):
        chunks.append({
            "type": "policy_update",
            "name": update.get("title", ""),
            "content": json.dumps(update),
            "text": f"Policy update ({update.get('date')}): {update.get('title')} - {update.get('summary')}"
        })
    
    # Use ASI-1 Mini to rank relevance
    client = OpenAI(base_url="https://api.asi1.ai/v1", api_key=api_key)
    
    chunk_texts = "\n".join([f"{i+1}. {c['text']}" for i, c in enumerate(chunks)])
    
    response = client.chat.completions.create(
        model="asi1-mini",
        messages=[
            {"role": "system", "content": "You are a search relevance ranker. Given a query and numbered items, return the numbers of the most relevant items in order of relevance. Return only comma-separated numbers, nothing else."},
            {"role": "user", "content": f"Query: {query}\n\nItems:\n{chunk_texts}\n\nReturn the {top_k} most relevant item numbers:"}
        ],
    )
    
    try:
        ranking_text = response.choices[0].message.content.strip()
        indices = [int(x.strip()) - 1 for x in ranking_text.split(",") if x.strip().isdigit()]
        return [chunks[i] for i in indices[:top_k] if 0 <= i < len(chunks)]
    except Exception:
        # Fallback: return first few chunks
        return chunks[:top_k]


def build_eligibility_context(profile: dict) -> str:
    """
    Build a context string with relevant benefits data for eligibility checking.
    """
    data = get_benefits_data()
    household_size = profile.get("household_size", 1)
    
    context_parts = [
        f"Federal Poverty Level (2025) for household of {household_size}: ${get_fpl(household_size)}/year",
        "",
        "BENEFITS DATA:",
    ]
    
    for benefit_name, benefit_info in data.get("benefits", {}).items():
        limit = get_income_limit(benefit_name, household_size)
        context_parts.append(f"\n{benefit_name}:")
        context_parts.append(f"  - Income limit: ${limit}/month for household of {household_size}")
        context_parts.append(f"  - Eligible statuses: {benefit_info.get('eligible_statuses', [])}")
        context_parts.append(f"  - Ineligible statuses: {benefit_info.get('ineligible_statuses', [])}")
        if benefit_info.get("all_immigration_eligible"):
            context_parts.append("  - NO immigration check required")
        if benefit_info.get("requires_children"):
            context_parts.append("  - Requires children under 18")
        if benefit_info.get("requires_wic_category"):
            context_parts.append(f"  - Requires: {benefit_info.get('wic_categories', [])}")
        if benefit_info.get("daca_state_programs"):
            context_parts.append(f"  - DACA state programs: {benefit_info.get('daca_state_programs', [])}")
    
    return "\n".join(context_parts)


def build_application_context(benefit_name: str, profile: dict) -> str:
    """
    Build context for application guidance.
    """
    benefit = get_benefit_info(benefit_name)
    if not benefit:
        return f"No data found for benefit: {benefit_name}"
    
    return f"""
BENEFIT: {benefit_name}
Full name: {benefit.get('name', benefit_name)}
Description: {benefit.get('description', '')}

APPLY URL: {benefit.get('apply_url', 'Check your state website')}

DOCUMENTS REQUIRED:
{chr(10).join('- ' + doc for doc in benefit.get('docs_required', []))}

PROCESSING TIME: {benefit.get('processing_time', 'Varies by state')}

COMMON REJECTIONS:
{chr(10).join('- ' + reason for reason in benefit.get('common_rejections', []))}

USER PROFILE:
- State: {profile.get('state', 'Unknown')}
- Immigration status: {profile.get('immigration_status', 'Unknown')}
- Has children: {profile.get('has_children', False)}
- Is pregnant: {profile.get('is_pregnant', False)}
"""


def build_policy_context(benefit_name: str = None) -> str:
    """
    Build context for policy updates.
    """
    data = get_benefits_data()
    updates = data.get("policy_updates", [])
    
    if benefit_name:
        updates = [u for u in updates if u.get("benefit") == benefit_name]
    
    if not updates:
        return "No recent policy updates found."
    
    context_parts = ["RECENT POLICY UPDATES:"]
    for update in updates:
        context_parts.append(f"\n[{update.get('date')}] {update.get('benefit')}: {update.get('title')}")
        context_parts.append(f"  {update.get('summary')}")
        if update.get('impact'):
            context_parts.append(f"  Impact: {update.get('impact')}")
    
    return "\n".join(context_parts)
