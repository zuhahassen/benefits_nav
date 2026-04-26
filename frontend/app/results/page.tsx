"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface BenefitResult {
  verdict: "likely" | "possible" | "ineligible";
  explanation: string;
}

interface ResultsData {
  reply: string;
  eligibility: Record<string, BenefitResult> | null;
  profile: Record<string, any>;
  navigator_guidance: string | null;
  agents_called: string[];
}

const verdictColors = {
  likely: { bg: "#e8f5e9", border: "#4caf50", text: "#2e7d32", label: "Likely Eligible" },
  possible: { bg: "#fff3e0", border: "#ff9800", text: "#e65100", label: "May Be Eligible" },
  ineligible: { bg: "#ffebee", border: "#f44336", text: "#c62828", label: "Likely Not Eligible" },
};

const benefitInfo: Record<string, { icon: string; fullName: string }> = {
  SNAP: { icon: "🛒", fullName: "Supplemental Nutrition Assistance Program" },
  Medicaid: { icon: "🏥", fullName: "Health Coverage" },
  TANF: { icon: "💵", fullName: "Temporary Assistance for Needy Families" },
  WIC: { icon: "🍼", fullName: "Women, Infants, and Children" },
  LIHEAP: { icon: "💡", fullName: "Low Income Home Energy Assistance" },
};

export default function ResultsPage() {
  const router = useRouter();
  const [results, setResults] = useState<ResultsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [applyingFor, setApplyingFor] = useState<string | null>(null);
  const [applicationGuide, setApplicationGuide] = useState<string | null>(null);
  const [policyAlerts, setPolicyAlerts] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("benefits_results");
    if (stored) {
      try {
        setResults(JSON.parse(stored));
      } catch (e) {
        console.error("Failed to parse results:", e);
      }
    }
    setLoading(false);
  }, []);

  async function handleApply(benefitId: string) {
    setApplyingFor(benefitId);
    setApplicationGuide(null);
    setPolicyAlerts(null);

    try {
      const res = await fetch("/api/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          benefit_id: benefitId,
          profile: results?.profile,
        }),
      });
      const data = await res.json();
      setApplicationGuide(data.application_guide || data.reply);
      setPolicyAlerts(data.policy_alerts);
    } catch (e) {
      setApplicationGuide("Sorry, we couldn't load the application guide. Please try again.");
    }
  }

  function closeGuide() {
    setApplyingFor(null);
    setApplicationGuide(null);
    setPolicyAlerts(null);
  }

  if (loading) {
    return (
      <div style={styles.page}>
        <div style={styles.loading}>Loading your results...</div>
      </div>
    );
  }

  if (!results) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <h1 style={styles.title}>No Results Found</h1>
          <p style={styles.subtitle}>Please complete the intake form first.</p>
          <button style={styles.primaryBtn} onClick={() => router.push("/intake")}>
            Start Over
          </button>
        </div>
      </div>
    );
  }

  const eligibility = results.eligibility || {};
  const sortedBenefits = Object.entries(eligibility).sort((a, b) => {
    const order = { likely: 0, possible: 1, ineligible: 2 };
    return (order[a[1].verdict] || 2) - (order[b[1].verdict] || 2);
  });

  const likelyCount = sortedBenefits.filter(([_, v]) => v.verdict === "likely").length;
  const possibleCount = sortedBenefits.filter(([_, v]) => v.verdict === "possible").length;

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.brand}>Bento</div>
          <div style={styles.agentsBadge}>
            Powered by {results.agents_called?.length || 1} AI agents
          </div>
        </div>

        {/* Summary */}
        <div style={styles.summaryCard}>
          <h1 style={styles.title}>Your Benefits Summary</h1>
          <p style={styles.summaryText}>
            Based on your information, you may qualify for{" "}
            <strong>{likelyCount} benefit{likelyCount !== 1 ? "s" : ""}</strong>
            {possibleCount > 0 && (
              <>, with {possibleCount} more worth exploring</>
            )}
            .
          </p>
        </div>

        {/* Benefits List */}
        <div style={styles.benefitsList}>
          {sortedBenefits.map(([name, result]) => {
            const colors = verdictColors[result.verdict];
            const info = benefitInfo[name] || { icon: "📋", fullName: name };

            return (
              <div
                key={name}
                style={{
                  ...styles.benefitCard,
                  borderLeftColor: colors.border,
                  background: colors.bg,
                }}
              >
                <div style={styles.benefitHeader}>
                  <span style={styles.benefitIcon}>{info.icon}</span>
                  <div>
                    <div style={styles.benefitName}>{name}</div>
                    <div style={styles.benefitFullName}>{info.fullName}</div>
                  </div>
                  <div
                    style={{
                      ...styles.verdictBadge,
                      background: colors.border,
                      color: "#fff",
                    }}
                  >
                    {colors.label}
                  </div>
                </div>
                <p style={{ ...styles.explanation, color: colors.text }}>
                  {result.explanation}
                </p>
                {result.verdict !== "ineligible" && (
                  <button
                    style={styles.applyBtn}
                    onClick={() => handleApply(name)}
                  >
                    How to Apply →
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* Navigator Guidance (for complex cases) */}
        {results.navigator_guidance && (
          <div style={styles.navigatorCard}>
            <div style={styles.navigatorHeader}>
              <span style={styles.navigatorIcon}>🧭</span>
              <span style={styles.navigatorTitle}>Navigator Guidance</span>
            </div>
            <p style={styles.navigatorText}>{results.navigator_guidance}</p>
          </div>
        )}

        {/* Application Guide Modal */}
        {applyingFor && applicationGuide && (
          <div style={styles.modalOverlay} onClick={closeGuide}>
            <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
              <button style={styles.closeBtn} onClick={closeGuide}>×</button>
              <h2 style={styles.modalTitle}>
                {benefitInfo[applyingFor]?.icon} How to Apply for {applyingFor}
              </h2>
              <div style={styles.guideContent}>
                {applicationGuide.split("\n").map((line, i) => (
                  <p key={i} style={styles.guideLine}>{line}</p>
                ))}
              </div>
              {policyAlerts && (
                <div style={styles.policyAlert}>
                  <div style={styles.alertHeader}>⚠️ Policy Updates</div>
                  <p style={styles.alertText}>{policyAlerts}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Footer */}
        <div style={styles.footer}>
          <button style={styles.secondaryBtn} onClick={() => router.push("/intake")}>
            ← Start Over
          </button>
          <div style={styles.disclaimer}>
            This is not official eligibility determination. Apply to confirm.
          </div>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: "#f5f5f5",
    fontFamily: "system-ui, -apple-system, sans-serif",
    color: "#000",
    padding: 24,
  },
  container: {
    maxWidth: 800,
    margin: "0 auto",
  },
  loading: {
    textAlign: "center",
    fontSize: 18,
    color: "#666",
    marginTop: 100,
  },
  card: {
    background: "#fff",
    borderRadius: 12,
    padding: 40,
    textAlign: "center",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 24,
  },
  brand: {
    fontSize: 28,
    fontWeight: 900,
  },
  agentsBadge: {
    background: "#e3f2fd",
    color: "#1565c0",
    padding: "6px 12px",
    borderRadius: 20,
    fontSize: 13,
    fontWeight: 600,
  },
  summaryCard: {
    background: "#fff",
    borderRadius: 12,
    padding: 32,
    marginBottom: 24,
    textAlign: "center",
  },
  title: {
    fontSize: 32,
    fontWeight: 800,
    marginBottom: 12,
  },
  subtitle: {
    fontSize: 16,
    color: "#666",
    marginBottom: 24,
  },
  summaryText: {
    fontSize: 18,
    color: "#333",
    lineHeight: 1.6,
  },
  benefitsList: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  benefitCard: {
    background: "#fff",
    borderRadius: 12,
    padding: 24,
    borderLeftWidth: 4,
    borderLeftStyle: "solid",
  },
  benefitHeader: {
    display: "flex",
    alignItems: "center",
    gap: 16,
    marginBottom: 12,
  },
  benefitIcon: {
    fontSize: 32,
  },
  benefitName: {
    fontSize: 20,
    fontWeight: 700,
  },
  benefitFullName: {
    fontSize: 14,
    color: "#666",
  },
  verdictBadge: {
    marginLeft: "auto",
    padding: "6px 12px",
    borderRadius: 20,
    fontSize: 13,
    fontWeight: 600,
  },
  explanation: {
    fontSize: 15,
    lineHeight: 1.6,
    marginBottom: 16,
  },
  applyBtn: {
    background: "#000",
    color: "#fff",
    border: "none",
    padding: "12px 20px",
    borderRadius: 8,
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
  },
  navigatorCard: {
    background: "#fff8e1",
    borderRadius: 12,
    padding: 24,
    marginTop: 24,
    borderLeftWidth: 4,
    borderLeftStyle: "solid",
    borderLeftColor: "#ffc107",
  },
  navigatorHeader: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    marginBottom: 12,
  },
  navigatorIcon: {
    fontSize: 24,
  },
  navigatorTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: "#f57f17",
  },
  navigatorText: {
    fontSize: 15,
    lineHeight: 1.6,
    color: "#5d4037",
  },
  modalOverlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: "rgba(0,0,0,0.5)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    zIndex: 1000,
  },
  modal: {
    background: "#fff",
    borderRadius: 16,
    padding: 32,
    maxWidth: 600,
    maxHeight: "80vh",
    overflow: "auto",
    position: "relative",
  },
  closeBtn: {
    position: "absolute",
    top: 16,
    right: 16,
    background: "none",
    border: "none",
    fontSize: 28,
    cursor: "pointer",
    color: "#999",
  },
  modalTitle: {
    fontSize: 24,
    fontWeight: 700,
    marginBottom: 20,
  },
  guideContent: {
    fontSize: 15,
    lineHeight: 1.8,
  },
  guideLine: {
    marginBottom: 12,
  },
  policyAlert: {
    background: "#fff3e0",
    borderRadius: 8,
    padding: 16,
    marginTop: 20,
  },
  alertHeader: {
    fontWeight: 700,
    marginBottom: 8,
    color: "#e65100",
  },
  alertText: {
    fontSize: 14,
    lineHeight: 1.6,
    color: "#5d4037",
  },
  footer: {
    marginTop: 32,
    textAlign: "center",
  },
  primaryBtn: {
    background: "#000",
    color: "#fff",
    border: "none",
    padding: "16px 32px",
    borderRadius: 8,
    fontSize: 16,
    fontWeight: 600,
    cursor: "pointer",
  },
  secondaryBtn: {
    background: "#fff",
    color: "#000",
    border: "2px solid #000",
    padding: "12px 24px",
    borderRadius: 8,
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
    marginBottom: 16,
  },
  disclaimer: {
    fontSize: 13,
    color: "#999",
    marginTop: 16,
  },
};
