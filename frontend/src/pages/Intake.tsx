import { useState } from "react";
import { api, type Extracted } from "../lib/api";
import { INTAKE_LANGUAGES, useT } from "../lib/i18n";
import { useRecorder } from "../lib/useRecorder";

const AGE_BANDS = ["0-12", "13-17", "18-40", "41-60", "61-70", "71-80", "80+"];

const empty = {
  report_type: "missing",
  person_name: "",
  gender: "",
  age_band: "",
  language: "Marathi",
  last_seen_location: "",
  physical_description: "",
  reporter_mobile: "",
  state: "",
  district: "",
};
type Form = typeof empty;
type Meta = { raw_text?: string; detected_language?: string; extraction_confidence?: number };

const inputCls =
  "w-full rounded-xl border border-[var(--color-line)] bg-white px-3.5 py-3 text-[15px] outline-none focus:ring-2 focus:ring-[var(--color-saffron)]/30";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm font-semibold">{label}</span>
      <div className="mt-1.5">{children}</div>
    </label>
  );
}

export default function Intake() {
  const t = useT();
  const [f, setF] = useState<Form>({ ...empty });
  const [meta, setMeta] = useState<Meta>({});
  const [done, setDone] = useState<{ case_id: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const rec = useRecorder();
  const [voiceStage, setVoiceStage] = useState<"" | "transcribing" | "thinking" | "done">("");
  const [transcript, setTranscript] = useState("");
  const [detLang, setDetLang] = useState<string | null>(null);
  const [freeText, setFreeText] = useState("");

  const set = (k: keyof Form, v: string) => setF((p) => ({ ...p, [k]: v }));

  const GENDERS = [
    { v: "Male", l: t("in.male") },
    { v: "Female", l: t("in.female") },
    { v: "Unknown", l: t("in.unknown") },
  ];

  function applyExtracted(ex: Extracted, rawText: string, detectedCode?: string | null): boolean {
    if (ex.confidence < 0.15) {
      alert("We couldn't extract any information from that. Please try describing the person's name, age, clothes, or where they were last seen.");
      return false;
    }
    setF((p) => ({
      ...p,
      person_name: ex.person_name ?? p.person_name,
      gender: ex.gender ?? p.gender,
      age_band: ex.age_band ?? p.age_band,
      language: ex.language ?? p.language,
      last_seen_location: ex.last_seen_location ?? p.last_seen_location,
      physical_description: ex.physical_description ?? p.physical_description,
      reporter_mobile: ex.reporter_mobile ?? p.reporter_mobile,
      state: ex.state ?? p.state,
      district: ex.district ?? p.district,
    }));
    setMeta({ raw_text: rawText, detected_language: detectedCode ?? undefined, extraction_confidence: ex.confidence });
    return true;
  }

  async function onMic() {
    if (rec.recording) {
      const blob = await rec.stop();
      try {
        setVoiceStage("transcribing");
        const tr = await api.transcribe(blob);
        setTranscript(tr.transcript);
        setDetLang(tr.language_name || tr.language_code);
        setVoiceStage("thinking");
        const ex = await api.extract(tr.transcript, tr.language_code);
        const ok = applyExtracted(ex, tr.transcript, tr.language_code);
        if (ok) {
          setVoiceStage("done");
        } else {
          setTranscript("");
          setVoiceStage("");
        }
      } catch (e) {
        alert("Voice processing failed: " + (e as Error).message);
        setVoiceStage("");
      }
    } else {
      setVoiceStage("");
      setTranscript("");
      rec.start();
    }
  }

  async function onAutofill() {
    if (!freeText.trim()) return;
    try {
      setVoiceStage("thinking");
      const ex = await api.extract(freeText);
      const ok = applyExtracted(ex, freeText);
      if (ok) {
        setTranscript(freeText);
        setVoiceStage("done");
      } else {
        setVoiceStage("");
      }
    } catch (e) {
      alert((e as Error).message);
      setVoiceStage("");
    }
  }

  async function submit() {
    setBusy(true);
    try {
      const res = await api.fileMissing({ ...f, ...meta });
      setDone(res);
    } catch (e) {
      alert("Could not file: " + (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="mx-auto max-w-lg py-10 text-center">
        <div className="card relative overflow-hidden p-8">
          <div className="nandi-gradient absolute inset-x-0 top-0 h-1.5" />
          <div className="text-5xl">🪷</div>
          <h2 className="mt-3 text-2xl font-extrabold">{t("in.filed")}</h2>
          <p className="mt-1 text-[var(--color-ink-soft)]">{t("in.filedSub")}</p>
          <div className="mt-4 inline-block rounded-xl bg-[var(--color-paper-2)] px-4 py-2 font-mono text-lg font-bold">{done.case_id}</div>
          <div className="mt-6">
            <button onClick={() => { setF({ ...empty }); setMeta({}); setTranscript(""); setVoiceStage(""); setDone(null); }} className="nandi-gradient rounded-full px-6 py-3 font-semibold text-white">
              {t("in.fileAnother")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const stageLabel =
    voiceStage === "transcribing" ? `${t("in.transcribing")}…`
    : voiceStage === "thinking" ? `${t("in.understanding")}…`
    : "";

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div>
        <h2 className="text-2xl font-extrabold">{t("in.title")}</h2>
        <p className="text-sm text-[var(--color-ink-soft)]">{t("in.sub")}</p>
      </div>

      {/* Voice-first capture */}
      <div className="card overflow-hidden">
        <div className="flex items-center gap-4 p-5">
          <button
            onClick={onMic}
            aria-label={rec.recording ? t("in.stopSpeaking") : t("in.speak")}
            className={`grid h-16 w-16 shrink-0 place-items-center rounded-full text-white transition ${rec.recording ? "bg-[var(--color-danger)] animate-halo" : "nandi-gradient"}`}
          >
            <span className="text-2xl">{rec.recording ? "■" : "🎤"}</span>
          </button>
          <div className="min-w-0">
            <div className="font-bold">{rec.recording ? t("in.stopSpeaking") : t("in.speak")}</div>
            <div className="text-sm text-[var(--color-ink-soft)]">
              {rec.recording ? t("in.recording") : t("in.speakHint")}
            </div>
            {stageLabel && <div className="mt-1 text-sm font-semibold text-[var(--color-saffron)] animate-livepulse">{stageLabel}</div>}
            {rec.error && <div className="mt-1 text-xs text-[var(--color-danger)]">{rec.error}</div>}
          </div>
        </div>

        {/* free-text fallback */}
        <div className="border-t border-[var(--color-line)] bg-[var(--color-paper-2)]/50 p-4">
          <div className="text-xs font-semibold text-[var(--color-ink-soft)]">{t("in.orType")}</div>
          <div className="mt-2 flex gap-2">
            <input className={inputCls + " flex-1"} value={freeText} onChange={(e) => setFreeText(e.target.value)}
              placeholder={t("in.typePlaceholder")} />
            <button onClick={onAutofill} className="rounded-xl bg-[var(--color-ink)] px-4 text-sm font-semibold text-white">{t("in.autofill")}</button>
          </div>
        </div>

        {transcript && (
          <div className="border-t border-[var(--color-line)] p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-[var(--color-ink-soft)]">
              {t("in.heard")} {detLang && <span className="rounded-full bg-[var(--color-paper-2)] px-2 py-0.5">{detLang}</span>}
              {meta.extraction_confidence != null && <span className="ml-auto">{t("in.confidence")} {Math.round(meta.extraction_confidence * 100)}%</span>}
            </div>
            <p className="mt-1 rounded-xl bg-[var(--color-paper-2)] p-3 text-sm">{transcript}</p>
            <p className="mt-1.5 text-xs text-[var(--color-ink-soft)]">{t("in.autofilled")}</p>
          </div>
        )}
      </div>

      {/* Structured form */}
      <div className="card space-y-4 p-5">
        <div className="flex gap-2">
          {[["missing", t("s.missing")], ["found", t("s.found")]].map(([v, label]) => (
            <button key={v} onClick={() => set("report_type", v)}
              className={`flex-1 rounded-xl border px-3 py-2.5 text-sm font-semibold ${f.report_type === v ? "border-transparent nandi-gradient text-white" : "border-[var(--color-line)] bg-white"}`}>
              {label}
            </button>
          ))}
        </div>

        <Field label={t("lang.label")}>
          <div className="flex flex-wrap gap-2">
            {INTAKE_LANGUAGES.map((l) => (
              <button key={l.code} onClick={() => set("language", l.label)}
                className={`rounded-full border px-3 py-1.5 text-sm ${f.language === l.label ? "border-transparent bg-[var(--color-ink)] text-white" : "border-[var(--color-line)] bg-white"}`}>
                {l.label}
              </button>
            ))}
          </div>
        </Field>

        <Field label={t("in.name")}>
          <input className={inputCls} value={f.person_name} onChange={(e) => set("person_name", e.target.value)} placeholder={t("in.namePlaceholder")} />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label={t("in.gender")}>
            <div className="flex gap-2">
              {GENDERS.map((g) => (
                <button key={g.v} onClick={() => set("gender", g.v)}
                  className={`flex-1 rounded-xl border px-2 py-2.5 text-sm ${f.gender === g.v ? "border-transparent bg-[var(--color-ink)] text-white" : "border-[var(--color-line)] bg-white"}`}>
                  {g.l}
                </button>
              ))}
            </div>
          </Field>
          <Field label={t("in.ageGroup")}>
            <select className={inputCls} value={f.age_band} onChange={(e) => set("age_band", e.target.value)}>
              <option value="">-</option>
              {AGE_BANDS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </Field>
        </div>

        <Field label={t("in.lastSeen")}>
          <input className={inputCls} value={f.last_seen_location} onChange={(e) => set("last_seen_location", e.target.value)} placeholder={t("in.lastSeenPlaceholder")} />
        </Field>

        <Field label={t("in.desc")}>
          <textarea className={inputCls} rows={3} value={f.physical_description} onChange={(e) => set("physical_description", e.target.value)} placeholder={t("in.descPlaceholder")} />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label={t("in.state")}>
            <input className={inputCls} value={f.state} onChange={(e) => set("state", e.target.value)} />
          </Field>
          <Field label={t("in.mobile")}>
            <input className={inputCls} value={f.reporter_mobile} onChange={(e) => set("reporter_mobile", e.target.value)} placeholder="+91…" />
          </Field>
        </div>

        <button onClick={submit} disabled={busy}
          className="nandi-gradient w-full rounded-xl py-4 text-lg font-bold text-white disabled:opacity-60">
          {busy ? `${t("in.filing")}…` : t("in.submit")}
        </button>
        <p className="text-center text-xs text-[var(--color-ink-soft)]">{t("in.privacy")}</p>
      </div>
    </div>
  );
}
