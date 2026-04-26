import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  const { benefit_id, profile } = await request.json();

  if (!benefit_id) {
    return NextResponse.json(
      { error: "benefit_id is required" },
      { status: 400 }
    );
  }

  const baseUrl = process.env.VERCEL_URL 
    ? `https://${process.env.VERCEL_URL}` 
    : 'http://localhost:3000';

  // Get application guidance from Bento
  const applyRes = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      intent: "apply",
      benefit_id,
      profile,
    }),
  });

  const applyData = await applyRes.json();

  // Also check for policy updates
  const policyRes = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      intent: "policy_check",
      benefit_id,
    }),
  });

  const policyData = await policyRes.json();

  return NextResponse.json({
    benefit_id,
    application_guide: applyData.reply,
    policy_alerts: policyData.reply,
    agents_called: ["bento", "application", "policy_watcher"],
  });
}
