"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

const questions = [
  {
    id: "state",
    text: "What state do you currently live in?",
    type: "select",
    options: [
      "Alabama","Alaska","Arizona","Arkansas","California","Colorado",
      "Connecticut","Delaware","Florida","Georgia","Hawaii","Idaho",
      "Illinois","Indiana","Iowa","Kansas","Kentucky","Louisiana",
      "Maine","Maryland","Massachusetts","Michigan","Minnesota",
      "Mississippi","Missouri","Montana","Nebraska","Nevada",
      "New Hampshire","New Jersey","New Mexico","New York",
      "North Carolina","North Dakota","Ohio","Oklahoma","Oregon",
      "Pennsylvania","Rhode Island","South Carolina","South Dakota",
      "Tennessee","Texas","Utah","Vermont","Virginia","Washington",
      "West Virginia","Wisconsin","Wyoming"
    ],
  },
  {
    id: "household_size",
    text: "How many people live in your household?",
    type: "stepper",
  },
  {
    id: "member_ages",
    text: "What are the ages of your household members?",
    type: "ages",
  },
  {
    id: "health_flags",
    text: "Does anyone in your household fit any of these?",
    type: "multicheck",
    options: [
      "Currently pregnant",
      "Postpartum (up to 6 months after pregnancy)",
      "Currently breastfeeding an infant under 1 year old",
      "Has a physical or mental disability that limits daily activities",
    ],
  },
  {
    id: "current_benefits",
    text: "Does your household currently receive any of these benefits?",
    type: "multicheck",
    options: [
      "SNAP / Food Stamps / EBT",
      "Medicaid or CHIP",
      "TANF / Cash Assistance",
    ],
  },
  {
    id: "income_range",
    text: "What is your household's total gross monthly income (before taxes)?",
    type: "slider",
  },
  {
    id: "housing",
    text: "How much does your household pay for rent or mortgage per month?",
    type: "number",
    placeholder: "e.g. 1200",
  },
  {
    id: "employment",
    text: "What is your current employment situation?",
    type: "radio",
    options: [
      "Working full-time (35+ hours/week)",
      "Working part-time (under 35 hours/week)",
      "Currently unemployed / looking for work",
      "Unable to work due to disability or caregiving",
      "Self-employed",
      "Student",
      "Retired",
    ],
  },
  {
    id: "immigration",
    text: "What is your residency or immigration status?",
    type: "radio",
    note: "This is only used to match you with eligible programs. It is never stored or shared.",
    options: [
      "U.S. citizen or U.S. national",
      "Lawful Permanent Resident (Green Card holder)",
      "DACA (Deferred Action for Childhood Arrivals)",
      "Refugee, asylee, or humanitarian status",
      "Other visa or immigration status",
      "Prefer not to say / not sure",
    ],
  },
];

export default function IntakePage() {
  const router = useRouter();
  const [stage, setStage] = useState<"landing" | "quiz">("landing");
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, any>>({
    household_size: 2,
    member_ages: ["18-25", "18-25"],
    health_flags: [],
    current_benefits: [],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const q = questions[step];

  function setAnswer(id: string, value: any) {
    setAnswers((prev) => ({ ...prev, [id]: value }));
  }

  function toggleCheck(id: string, option: string) {
    const current: string[] = answers[id] || [];
    if (current.includes(option)) {
      setAnswer(id, current.filter((o) => o !== option));
    } else {
      setAnswer(id, [...current, option]);
    }
  }

  function changeSize(delta: number) {
    const newSize = Math.max(1, Math.min(12, (answers.household_size || 1) + delta));
    const ages = Array.from({ length: newSize }, (_, i) => answers.member_ages?.[i] || "18-25");
    setAnswer("household_size", newSize);
    setAnswer("member_ages", ages);
  }

  async function handleNext() {
    const current = answers[q.id];

    if (q.type === "select" && !current) {
      setError("Please select an option before continuing.");
      return;
    }
    if (q.type === "radio" && !current) {
      setError("Please select an option before continuing.");
      return;
    }
    if (q.type === "number" && !current) {
      setError("Please enter an amount before continuing.");
      return;
    }

    setError("");

    if (step < questions.length - 1) {
      setStep(step + 1);
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/intake", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(answers),
      });
      const data = await res.json();
      localStorage.setItem("benefits_results", JSON.stringify(data));
      router.push("/results");
    } catch (e) {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  // =========================
  // LANDING
  // =========================
  if (stage === "landing") {
    return (
      <div style={styles.page}>
        <div style={styles.landingCard}>
          <div style={styles.brand}>Bento</div>
          <div style={styles.tagline}>Find benefits you may qualify for in minutes</div>
          <div style={styles.buttonStack}>
            <button style={styles.primaryBtn}>Create account</button>
            <button style={styles.secondaryBtn} onClick={() => setStage("quiz")}>
              Continue as guest
            </button>
          </div>
        </div>
      </div>
    );
  }

  // =========================
  // QUIZ
  // =========================
  return (
    <div style={styles.page}>
      <div style={styles.quizCard}>

        {/* Progress */}
        <div style={styles.progress}>Question {step + 1} of {questions.length}</div>
        <div style={styles.progressBarWrap}>
          <div style={{ ...styles.progressBarFill, width: `${Math.round(((step + 1) / questions.length) * 100)}%` }} />
        </div>

        {/* Question text */}
        <div style={styles.question}>{q.text}</div>

        {/* Privacy note (immigration question) */}
        {"note" in q && q.note && (
          <div style={styles.privacyNote}>{q.note}</div>
        )}

        {/* SELECT */}
        {q.type === "select" && (
          <select
            style={styles.input}
            value={answers[q.id] || ""}
            onChange={(e) => setAnswer(q.id, e.target.value)}
          >
            <option value="">Select your state...</option>
            {q.options?.map((o) => <option key={o}>{o}</option>)}
          </select>
        )}

        {/* STEPPER */}
        {q.type === "stepper" && (
          <div style={styles.stepper}>
            <button style={styles.stepBtn} onClick={() => changeSize(-1)}>-</button>
            <div style={styles.bigNumber}>{answers.household_size}</div>
            <button style={styles.stepBtn} onClick={() => changeSize(1)}>+</button>
          </div>
        )}

        {/* AGES */}
        {q.type === "ages" && (
          <div style={styles.ageBox}>
            {Array.from({ length: answers.household_size || 1 }).map((_, i) => (
              <div key={i} style={styles.ageRow}>
                <span style={styles.ageLabel}>Person {i + 1}</span>
                <select
                  style={styles.ageSelect}
                  value={answers.member_ages?.[i] || "18-25"}
                  onChange={(e) => {
                    const ages = [...(answers.member_ages || [])];
                    ages[i] = e.target.value;
                    setAnswer("member_ages", ages);
                  }}
                >
                  <option>Under 1</option>
                  <option>1-4</option>
                  <option>5-12</option>
                  <option>13-17</option>
                  <option>18-25</option>
                  <option>26-40</option>
                  <option>41-59</option>
                  <option>60+</option>
                </select>
              </div>
            ))}
          </div>
        )}

        {/* MULTICHECK */}
        {q.type === "multicheck" && (
          <div style={styles.optionList}>
            {q.options?.map((o) => {
              const selected = (answers[q.id] || []).includes(o);
              return (
                <div
                  key={o}
                  style={{ ...styles.optionItem, ...(selected ? styles.optionSelected : {}) }}
                  onClick={() => toggleCheck(q.id, o)}
                >
                  <div style={{ ...styles.checkbox, ...(selected ? styles.checkboxSelected : {}) }}>
                    {selected && <span style={styles.checkmark}>✓</span>}
                  </div>
                  <span>{o}</span>
                </div>
              );
            })}
            {/* None of the above */}
            <div
              style={{ ...styles.optionItem, ...((answers[q.id] || []).length === 0 ? styles.optionSelected : {}) }}
              onClick={() => setAnswer(q.id, [])}
            >
              <div style={{ ...styles.checkbox, ...((answers[q.id] || []).length === 0 ? styles.checkboxSelected : {}) }}>
                {(answers[q.id] || []).length === 0 && <span style={styles.checkmark}>✓</span>}
              </div>
              <span>None of the above</span>
            </div>
          </div>
        )}

        {/* SLIDER */}
        {q.type === "slider" && (
          <div style={{ marginBottom: 32 }}>
            <div style={{ fontSize: 48, fontWeight: 900, textAlign: "center", marginBottom: 8 }}>
              {answers.income_range >= 5000
                ? "Over $5,000"
                : `$${(answers.income_range || 0).toLocaleString()}`}
            </div>
            <div style={{ fontSize: 15, color: "#999", textAlign: "center", marginBottom: 28 }}>
              per month, before taxes
            </div>
            <input
              type="range"
              min={0}
              max={5000}
              step={50}
              value={answers.income_range || 0}
              onChange={(e) => setAnswer("income_range", Number(e.target.value))}
              style={{ width: "100%", height: 6, cursor: "pointer", accentColor: "#000" }}
            />
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "#999", marginTop: 8 }}>
              <span>$0</span>
              <span>$1,000</span>
              <span>$2,000</span>
              <span>$3,000</span>
              <span>$4,000</span>
              <span>Over $5,000</span>
            </div>
          </div>
        )}

        {/* RADIO */}
        {q.type === "radio" && (
          <div style={styles.optionList}>
            {q.options?.map((o) => {
              const selected = answers[q.id] === o;
              return (
                <div
                  key={o}
                  style={{ ...styles.optionItem, ...(selected ? styles.optionSelected : {}) }}
                  onClick={() => setAnswer(q.id, o)}
                >
                  <div style={{ ...styles.radio, ...(selected ? styles.radioSelected : {}) }}>
                    {selected && <div style={styles.radioDot} />}
                  </div>
                  <span>{o}</span>
                </div>
              );
            })}
          </div>
        )}

        {/* NUMBER */}
        {q.type === "number" && (
          <div style={styles.inputWrap}>
            <span style={styles.prefix}>$</span>
            <input
              style={styles.numberInput}
              type="number"
              placeholder={"placeholder" in q ? (q as any).placeholder : ""}
              value={answers[q.id] || ""}
              onChange={(e) => setAnswer(q.id, e.target.value)}
            />
          </div>
        )}

        {error && <div style={styles.error}>{error}</div>}

        {/* Nav buttons */}
        <div style={styles.nav}>
          {step > 0 && (
            <button style={styles.backBtn} onClick={() => setStep(step - 1)}>Back</button>
          )}
          <button style={styles.nextBtn} onClick={handleNext} disabled={loading}>
            {loading ? "Finding your benefits..." : step === questions.length - 1 ? "See my results" : "Continue"}
          </button>
        </div>

      </div>
    </div>
  );
}

// =========================
// STYLES
// =========================
const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#fff", display: "flex", justifyContent: "center", alignItems: "center", fontFamily: "system-ui, -apple-system, sans-serif", color: "#000", padding: 32 },
  landingCard: { textAlign: "center", maxWidth: 440 },
  brand: { fontSize: 54, fontWeight: 900, marginBottom: 10 },
  tagline: { fontSize: 18, fontWeight: 500, marginBottom: 24 },
  buttonStack: { display: "flex", flexDirection: "column", gap: 12 },
  primaryBtn: { padding: 16, background: "#000", color: "#fff", fontSize: 17, fontWeight: 700, border: "none", cursor: "pointer" },
  secondaryBtn: { padding: 16, background: "#fff", borderWidth: 2, borderStyle: "solid", borderColor: "#000", fontSize: 17, fontWeight: 700, cursor: "pointer" },
  quizCard: { width: "100%", maxWidth: 720 },
  progress: { fontSize: 16, fontWeight: 600, color: "#888", marginBottom: 10 },
  progressBarWrap: { height: 4, background: "#eee", borderRadius: 99, marginBottom: 36 },
  progressBarFill: { height: "100%", background: "#000", borderRadius: 99, transition: "width 0.3s ease" },
  question: { fontSize: 34, fontWeight: 800, marginBottom: 28, lineHeight: 1.25 },
  privacyNote: { background: "#f5f5f5", borderRadius: 8, padding: "14px 18px", fontSize: 15, color: "#000", marginBottom: 20, lineHeight: 1.5 },
  input: { width: "100%", padding: 18, fontSize: 18, borderWidth: 1, borderStyle: "solid", borderColor: "#ddd", marginBottom: 20, borderRadius: 6 },
  stepper: { display: "flex", justifyContent: "center", alignItems: "center", gap: 32, marginBottom: 32 },
  bigNumber: { fontSize: 80, fontWeight: 900, lineHeight: 1 },
  stepBtn: { width: 60, height: 60, borderWidth: 1, borderStyle: "solid", borderColor: "#ddd", background: "#fff", fontSize: 28, cursor: "pointer", borderRadius: 6 },
  ageBox: { display: "flex", flexDirection: "column", gap: 12, marginBottom: 24 },
  ageRow: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 },
  ageLabel: { fontSize: 17, fontWeight: 600, minWidth: 90 },
  ageSelect: { flex: 1, padding: "13px 16px", fontSize: 17, borderWidth: 1, borderStyle: "solid", borderColor: "#ddd", borderRadius: 6 },
  optionList: { display: "flex", flexDirection: "column", gap: 10, marginBottom: 24 },
  optionItem: { display: "flex", alignItems: "center", gap: 16, padding: "17px 20px", borderWidth: 1.5, borderStyle: "solid", borderColor: "#ddd", borderRadius: 10, cursor: "pointer", fontSize: 17 },
  optionSelected: { borderColor: "#000", background: "#f5f5f5" },
  checkbox: { width: 26, height: 26, borderWidth: 1.5, borderStyle: "solid", borderColor: "#ccc", borderRadius: 5, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "white" },
  checkboxSelected: { background: "#000", borderColor: "#000" },
  checkmark: { color: "white", fontSize: 15, fontWeight: 700 },
  radio: { width: 26, height: 26, borderWidth: 1.5, borderStyle: "solid", borderColor: "#ccc", borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "white" },
  radioSelected: { borderColor: "#000" },
  radioDot: { width: 13, height: 13, borderRadius: "50%", background: "#000" },
  inputWrap: { position: "relative", marginBottom: 24 },
  prefix: { position: "absolute", left: 16, top: "50%", transform: "translateY(-50%)", color: "#999", fontSize: 18 },
  numberInput: { width: "100%", padding: "16px 20px 16px 32px", fontSize: 18, borderWidth: 1, borderStyle: "solid", borderColor: "#ddd", borderRadius: 6, outline: "none" },
  skipLink: { textAlign: "center", fontSize: 15, color: "#999", cursor: "pointer", marginBottom: 20, textDecoration: "underline" },
  error: { color: "#c0392b", fontSize: 15, marginBottom: 14 },
  nav: { display: "flex", gap: 16, marginTop: 12 },
  backBtn: { flex: 1, padding: 20, borderWidth: 1, borderStyle: "solid", borderColor: "#ddd", background: "#fff", fontSize: 18, fontWeight: 700, cursor: "pointer", borderRadius: 6 },
  nextBtn: { flex: 1, padding: 20, background: "#000", color: "#fff", fontSize: 18, fontWeight: 700, border: "none", cursor: "pointer", borderRadius: 6 },
};