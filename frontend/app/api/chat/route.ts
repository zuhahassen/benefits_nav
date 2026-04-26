import { NextRequest, NextResponse } from "next/server";

// Agent addresses on Agentverse
const AGENT_ADDRESSES = {
  bento: process.env.BENTO_AGENT_ADDRESS || "agent1qwjaf2znjpkndh8xttkt2q2n0cfdedy6ntmp72h998pzwn2mwcwuuy8e82c",
  eligibility: "agent1qfqwm8m0fxaehg2denssmehr32etc6tyjl4079fnfy5cqnyzrt2auynq9u3",
  application: "agent1qv3jz94qczu93eyvuunf0ma6wumg4h4jta6prxefd7rt3r3nmktdzu9fhg6",
  policy_watcher: "agent1qd8ks3rlfpa4rcuy803ar3kdkk7lpye3td882e95juqx7fylw8jms46k5ud",
  navigator: "agent1qvshm6xkg0tpxga0xz3el0zlpa3rdeyytxttv6zfqjx9dp3s6pvc7dvjx5e",
};

/**
 * Call an Agentverse agent via ASI-1 Mini API
 * The agent_address parameter routes the request to the actual agent on Agentverse
 */
async function callAgentverse(
  agentAddress: string,
  message: string
): Promise<{ reply: string; raw: any }> {
  console.log(`[Agentverse] Calling agent: ${agentAddress.slice(0, 20)}...`);
  
  const response = await fetch("https://api.asi1.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.ASI1_API_KEY}`,
    },
    body: JSON.stringify({
      model: "asi1-mini",
      messages: [{ role: "user", content: message }],
      agent_address: agentAddress,
    }),
  });

  const data = await response.json();
  
  if (!response.ok) {
    console.error(`[Agentverse] Error from ${agentAddress}:`, data);
    throw new Error(data.message || "Agent call failed");
  }

  const reply = data.choices?.[0]?.message?.content ?? "";
  console.log(`[Agentverse] Response received (${reply.length} chars)`);
  
  return { reply, raw: data };
}

// Check if profile indicates a complex case needing NavigatorAgent
function isComplexCase(profile: any): boolean {
  const complexStatuses = ["daca", "undocumented", "visa", "lpr_under5yr", "unknown"];
  return complexStatuses.includes(profile?.immigration_status);
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { message, intent, profile, benefit_id } = body;

  console.log(`[Bento] Received request - intent: ${intent || "chat"}`);

  try {
    // ═══════════════════════════════════════════════════════════════════════
    // FLOW: Intake → Bento → EligibilityAgent → (NavigatorAgent if complex)
    // ═══════════════════════════════════════════════════════════════════════

    if (intent === "eligibility" && profile) {
      console.log("[Bento] Routing to EligibilityAgent on Agentverse");

      // Step 1: Call EligibilityAgent on Agentverse
      const { reply: eligibilityResponse } = await callAgentverse(
        AGENT_ADDRESSES.eligibility,
        JSON.stringify(profile)
      );

      // Parse eligibility JSON from agent response
      let eligibility = null;
      try {
        // Try to extract JSON from markdown code blocks first
        let jsonStr = eligibilityResponse;
        const codeBlockMatch = eligibilityResponse.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
        if (codeBlockMatch) {
          jsonStr = codeBlockMatch[1];
        }
        // Find the JSON object
        const jsonMatch = jsonStr.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          const parsed = JSON.parse(jsonMatch[0]);
          // Validate it has the expected structure
          if (parsed.SNAP || parsed.Medicaid || parsed.TANF || parsed.WIC || parsed.LIHEAP) {
            eligibility = parsed;
          }
        }
      } catch (e) {
        console.error("[Bento] Failed to parse eligibility JSON:", e);
      }

      // If no structured eligibility, create a basic one from the response
      if (!eligibility) {
        console.log("[Bento] Creating fallback eligibility from response text");
        eligibility = {
          SNAP: { verdict: "possible", explanation: "Please see the detailed response for eligibility information." },
          Medicaid: { verdict: "possible", explanation: "Please see the detailed response for eligibility information." },
          TANF: { verdict: "possible", explanation: "Please see the detailed response for eligibility information." },
          WIC: { verdict: "possible", explanation: "Please see the detailed response for eligibility information." },
          LIHEAP: { verdict: "possible", explanation: "Please see the detailed response for eligibility information." },
        };
      }

      // Step 2: If complex case, also call NavigatorAgent
      let navigatorResponse = null;
      if (isComplexCase(profile)) {
        console.log("[Bento] Complex case detected, routing to NavigatorAgent on Agentverse");
        const { reply } = await callAgentverse(
          AGENT_ADDRESSES.navigator,
          JSON.stringify({
            profile,
            situation: "Complex immigration status — determine available benefits",
            eligibility_results: eligibilityResponse,
          })
        );
        navigatorResponse = reply;
      }

      return NextResponse.json({
        reply: eligibilityResponse,
        eligibility,
        profile,
        navigator_guidance: navigatorResponse,
        agents_called: ["bento", "eligibility", ...(navigatorResponse ? ["navigator"] : [])],
      });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FLOW: Apply → Bento → ApplicationAgent → PolicyWatcherAgent
    // ═══════════════════════════════════════════════════════════════════════

    if (intent === "apply" && benefit_id) {
      console.log(`[Bento] Routing to ApplicationAgent on Agentverse for ${benefit_id}`);

      // Step 1: Call ApplicationAgent on Agentverse
      const { reply: applicationResponse } = await callAgentverse(
        AGENT_ADDRESSES.application,
        JSON.stringify({ benefit: benefit_id, profile: profile || {} })
      );

      // Step 2: Call PolicyWatcherAgent for alerts
      console.log("[Bento] Checking PolicyWatcherAgent on Agentverse for alerts");
      const { reply: policyResponse } = await callAgentverse(
        AGENT_ADDRESSES.policy_watcher,
        JSON.stringify({ benefit: benefit_id, state: profile?.state })
      );

      return NextResponse.json({
        reply: applicationResponse,
        policy_alerts: policyResponse,
        benefit_id,
        agents_called: ["bento", "application", "policy_watcher"],
      });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FLOW: Policy Check → PolicyWatcherAgent
    // ═══════════════════════════════════════════════════════════════════════

    if (intent === "policy_check" && benefit_id) {
      console.log(`[Bento] Routing to PolicyWatcherAgent on Agentverse for ${benefit_id}`);

      const { reply: policyResponse } = await callAgentverse(
        AGENT_ADDRESSES.policy_watcher,
        JSON.stringify({ benefit: benefit_id })
      );

      return NextResponse.json({
        reply: policyResponse,
        agents_called: ["bento", "policy_watcher"],
      });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FLOW: Navigate → NavigatorAgent (additional benefits, complex cases)
    // ═══════════════════════════════════════════════════════════════════════

    if (intent === "navigate" && profile) {
      console.log("[Bento] Routing to NavigatorAgent on Agentverse");

      const { reply: navigatorResponse } = await callAgentverse(
        AGENT_ADDRESSES.navigator,
        JSON.stringify({ profile, situation: "Suggest additional benefits" })
      );

      return NextResponse.json({
        reply: navigatorResponse,
        agents_called: ["bento", "navigator"],
      });
    }

    // ═══════════════════════════════════════════════════════════════════════
    // DEFAULT: General chat → Bento orchestrator on Agentverse
    // ═══════════════════════════════════════════════════════════════════════

    console.log("[Bento] Routing to Bento orchestrator on Agentverse");
    const { reply: bentoResponse } = await callAgentverse(
      AGENT_ADDRESSES.bento,
      message || "Hello"
    );

    return NextResponse.json({
      reply: bentoResponse,
      agents_called: ["bento"],
    });

  } catch (error) {
    console.error("[Bento] Error:", error);
    return NextResponse.json(
      { reply: "Sorry, I encountered an error. Please try again.", error: String(error) },
      { status: 500 }
    );
  }
}
