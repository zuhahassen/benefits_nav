import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const { message } = await req.json();

  const response = await fetch("https://api.asi1.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${process.env.ASI1_API_KEY}`,
    },
    body: JSON.stringify({
      model: "asi1-mini",
      messages: [{ role: "user", content: message }],
      agent_address: process.env.BENTO_AGENT_ADDRESS,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    console.error("ASI-1 API error:", data);
    return NextResponse.json(
      { reply: "Error contacting Bento.", error: data },
      { status: response.status }
    );
  }

  const reply = data.choices?.[0]?.message?.content ?? "No response from Bento.";

  return NextResponse.json({ reply });
}
