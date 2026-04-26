import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  const { profile } = await request.json();

  if (!profile) {
    return NextResponse.json(
      { error: "profile is required" },
      { status: 400 }
    );
  }

  const baseUrl = process.env.VERCEL_URL 
    ? `https://${process.env.VERCEL_URL}` 
    : 'http://localhost:3000';

  // Get eligibility from Bento
  const res = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      intent: "eligibility",
      profile,
    }),
  });

  const data = await res.json();

  // Also get navigator suggestions for additional benefits
  const navRes = await fetch(`${baseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      intent: "navigate",
      profile,
    }),
  });

  const navData = await navRes.json();

  return NextResponse.json({
    profile,
    eligibility: data.eligibility || null,
    explanation: data.reply,
    additional_benefits: navData.reply,
  });
}
