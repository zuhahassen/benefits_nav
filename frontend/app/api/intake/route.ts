import { NextRequest, NextResponse } from 'next/server';

function transformIntakeToProfile(intake: any) {
  const ages = intake.member_ages || [];
  const hasChildUnder5 = ages.some((age: string) => 
    ["Under 1", "1-4"].includes(age)
  );
  const hasChildUnder18 = ages.some((age: string) => 
    ["Under 1", "1-4", "5-12", "13-17"].includes(age)
  );

  const healthFlags = intake.health_flags || [];
  const currentBenefits = intake.current_benefits || [];

  const immigrationMap: Record<string, string> = {
    "U.S. citizen or U.S. national": "citizen",
    "Lawful Permanent Resident (Green Card holder)": "lpr_5yr",
    "DACA (Deferred Action for Childhood Arrivals)": "daca",
    "Refugee, asylee, or humanitarian status": "refugee",
    "Other visa or immigration status": "visa",
    "Prefer not to say / not sure": "unknown",
  };

  const benefitsMap: Record<string, string> = {
    "SNAP / Food Stamps / EBT": "SNAP",
    "Medicaid or CHIP": "Medicaid",
    "TANF / Cash Assistance": "TANF",
  };

  return {
    state: intake.state || "",
    household_size: intake.household_size || 1,
    monthly_income: intake.income_range || 0,
    housing_cost: parseInt(intake.housing) || 0,
    immigration_status: immigrationMap[intake.immigration] || "unknown",
    employment: intake.employment || "",
    has_children: hasChildUnder18,
    has_child_under_5: hasChildUnder5,
    is_pregnant: healthFlags.includes("Currently pregnant"),
    is_postpartum: healthFlags.includes("Postpartum (up to 6 months after pregnancy)"),
    is_breastfeeding: healthFlags.includes("Currently breastfeeding an infant under 1 year old"),
    has_disability: healthFlags.includes("Has a physical or mental disability that limits daily activities"),
    current_benefits: currentBenefits.map((b: string) => benefitsMap[b] || b),
    member_ages: ages,
  };
}

export async function POST(request: NextRequest) {
  const intake = await request.json();

  // Transform intake form answers into a structured profile
  const profile = transformIntakeToProfile(intake);

  // Call the chat API with eligibility intent
  const baseUrl = process.env.VERCEL_URL 
    ? `https://${process.env.VERCEL_URL}` 
    : 'http://localhost:3000';

  const res = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      intent: "eligibility",
      profile,
    }),
  });

  const data = await res.json();

  // Return eligibility results with the profile
  return NextResponse.json({
    profile,
    eligibility: data.eligibility || null,
    reply: data.reply,
    navigator_guidance: data.navigator_guidance || null,
    agents_called: data.agents_called || [],
  });
}
