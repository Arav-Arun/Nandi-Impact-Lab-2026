import { useState } from "react";
import { api, type Extracted } from "../lib/api";
import { useT, useLang, LANGUAGES } from "../lib/i18n";
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
type Meta = { raw_text?: string; detected_language?: string; extraction_confidence?: number; photo_url?: string };

function MicIcon({ on }: { on: boolean }) {
  return on ? <span className="block h-3.5 w-3.5 rounded-[3px] bg-white" /> : (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  );
}
function CameraIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 8a2 2 0 0 1 2-2h2l1.5-2h7L19 6h0a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><circle cx="12" cy="12.5" r="3.2" />
    </svg>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-[12px] font-semibold uppercase tracking-wide text-[var(--ink-faint)]">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

export default function Intake() {
  const t = useT();
  const { lang } = useLang();
  const [f, setF] = useState<Form>(() => ({
    ...empty,
    language: LANGUAGES.find((l) => l.code === lang)?.label ?? "Marathi",
  }));
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
      alert(t("in.autofilled"));
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
    setMeta((m) => ({ ...m, raw_text: rawText, detected_language: detectedCode ?? undefined, extraction_confidence: ex.confidence }));
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
        setVoiceStage(ok ? "done" : "");
        if (!ok) setTranscript("");
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
    const text = freeText.trim();
    if (!text) return;
    try {
      setVoiceStage("thinking");
      const ex = await api.extract(text);
      const ok = applyExtracted(ex, text);
      setTranscript(ok ? text : "");
      setVoiceStage(ok ? "done" : "");
    } catch (e) {
      alert((e as Error).message);
      setVoiceStage("");
    }
  }

  async function onPhoto(file: File) {
    try {
      setBusy(true);
      const res = await api.uploadPhoto(file);
      setMeta((m) => ({ ...m, photo_url: res.photo_url }));
      if (res.description) {
        setF((prev) => ({
          ...prev,
          physical_description: prev.physical_description ? `${prev.physical_description}\n[photo] ${res.description}` : res.description || "",
        }));
      }
    } catch (err) {
      alert("Upload failed: " + (err as Error).message);
    } finally {
      setBusy(false);
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
      <div className="mx-auto max-w-md py-12 text-center">
        <div className="panel p-8">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-[var(--ok-soft)] text-[var(--ok)]">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 13l4 4L19 7" /></svg>
          </div>
          <h2 className="mt-3 text-[20px] font-extrabold">{t("in.filed")}</h2>
          <p className="mt-1 text-[13px] text-[var(--ink-soft)]">{t("in.filedSub")}</p>
          <div className="mt-4">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--ink-faint)]">{t("in.caseId")}</div>
            <div className="mono mt-1 inline-block rounded-md bg-[var(--surface-2)] px-4 py-2 text-[18px] font-bold">{done.case_id}</div>
          </div>
          <button
            onClick={() => { setF({ ...empty }); setMeta({}); setTranscript(""); setVoiceStage(""); setDone(null); }}
            className="btn btn-primary mt-6"
          >
            {t("in.fileAnother")}
          </button>
        </div>
      </div>
    );
  }

  const stageLabel =
    voiceStage === "transcribing" ? `${t("in.transcribing")}…`
    : voiceStage === "thinking" ? `${t("in.understanding")}…` : "";

  return (
    <div className="mx-auto max-w-xl space-y-3">
      <div>
        <h1 className="text-[20px] font-extrabold tracking-tight">{t("in.title")}</h1>
        <p className="text-[13px] text-[var(--ink-soft)]">{t("in.sub")}</p>
      </div>

      {/* Voice-first capture */}
      <div className="panel overflow-hidden">
        <div className="flex items-center gap-4 p-4">
          <button
            onClick={onMic}
            aria-label={rec.recording ? t("in.stopSpeaking") : t("in.speak")}
            className={`grid h-14 w-14 shrink-0 place-items-center rounded-full text-white transition ${rec.recording ? "bg-[var(--danger)] animate-halo" : "bg-[var(--accent)]"}`}
          >
            <MicIcon on={rec.recording} />
          </button>
          <div className="min-w-0">
            <div className="text-[15px] font-bold">{rec.recording ? t("in.stopSpeaking") : t("in.speak")}</div>
            <div className="text-[13px] text-[var(--ink-soft)]">{rec.recording ? t("in.recording") : t("in.speakHint")}</div>
            {stageLabel && <div className="mt-0.5 text-[13px] font-semibold text-[var(--accent-ink)] animate-livepulse">{stageLabel}</div>}
            {rec.error && <div className="mt-0.5 text-[12px] text-[var(--danger)]">{rec.error}</div>}
          </div>
        </div>

        <div className="border-t border-[var(--line)] bg-[var(--surface-2)] p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--ink-faint)]">{t("in.orType")}</div>
          <div className="mt-1.5 flex gap-2">
            <input className="field flex-1" value={freeText} onChange={(e) => setFreeText(e.target.value)} placeholder={t("in.typePlaceholder")} />
            <button onClick={onAutofill} disabled={!freeText.trim()} className="btn btn-ink">{t("in.autofill")}</button>
          </div>
        </div>

        {transcript && (
          <div className="border-t border-[var(--line)] p-3">
            <div className="flex items-center gap-2 text-[11px] font-semibold text-[var(--ink-soft)]">
              {t("in.heard")} {detLang && <span className="rounded bg-[var(--surface-2)] px-1.5 py-0.5">{detLang}</span>}
              {meta.extraction_confidence != null && <span className="mono ml-auto">{t("in.confidence")} {Math.round(meta.extraction_confidence * 100)}%</span>}
            </div>
            <p className="mt-1 rounded-md bg-[var(--surface-2)] p-2.5 text-[13px]">{transcript}</p>
            <p className="mt-1 text-[12px] text-[var(--ink-soft)]">{t("in.autofilled")}</p>
          </div>
        )}
      </div>

      {/* Structured form */}
      <div className="panel space-y-3.5 p-4">
        <Field label={t("lang.label")}>
          <select className="field" value={f.language} onChange={(e) => set("language", e.target.value)}>
            {LANGUAGES.map((l) => <option key={l.code} value={l.label}>{l.native} · {l.label}</option>)}
          </select>
        </Field>

        <Field label={t("in.name")}>
          <input className="field" value={f.person_name} onChange={(e) => set("person_name", e.target.value)} placeholder={t("in.namePlaceholder")} />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label={t("in.gender")}>
            <div className="flex gap-1.5">
              {GENDERS.map((g) => (
                <button key={g.v} onClick={() => set("gender", g.v)}
                  className={`flex h-11 flex-1 items-center justify-center rounded-md border px-1 text-[13px] font-semibold ${f.gender === g.v ? "border-[var(--ink)] bg-[var(--ink)] text-white" : "border-[var(--line-strong)] bg-[var(--surface)]"}`}>
                  {g.l}
                </button>
              ))}
            </div>
          </Field>
          <Field label={t("in.ageGroup")}>
            <select className="field h-11" value={f.age_band} onChange={(e) => set("age_band", e.target.value)}>
              <option value="">-</option>
              {AGE_BANDS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </Field>
        </div>

        <Field label={t("in.lastSeen")}>
          <input className="field" value={f.last_seen_location} onChange={(e) => set("last_seen_location", e.target.value)} placeholder={t("in.lastSeenPlaceholder")} />
        </Field>

        <Field label={t("in.desc")}>
          <textarea className="field" rows={3} value={f.physical_description} onChange={(e) => set("physical_description", e.target.value)} placeholder={t("in.descPlaceholder")} />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label={t("in.state")}>
            <input className="field" value={f.state} onChange={(e) => set("state", e.target.value)} />
          </Field>
          <Field label={t("in.mobile")}>
            <input className="field" value={f.reporter_mobile} onChange={(e) => set("reporter_mobile", e.target.value)} placeholder="+91…" />
          </Field>
        </div>

        <Field label={t("in.photo")}>
          <div className="flex items-center justify-center gap-2.5">
            <input type="file" accept="image/*" capture="environment" className="hidden" id="intake-photo"
              onChange={(e) => { const file = e.target.files?.[0]; if (file) onPhoto(file); }} />
            <label htmlFor="intake-photo" className="btn btn-ghost"><CameraIcon /> {t("in.photoAdd")}</label>
            {meta.photo_url && (
              <>
                <img src={meta.photo_url} alt="" onError={(e) => { e.currentTarget.style.display = "none"; }} className="h-10 w-10 rounded-md border border-[var(--line)] object-cover" />
                <button type="button" onClick={() => setMeta((m) => ({ ...m, photo_url: undefined }))} className="text-[12px] font-semibold text-[var(--danger)]">{t("in.photoRemove")}</button>
              </>
            )}
          </div>
        </Field>

        <button onClick={submit} disabled={busy} className="btn btn-primary w-full py-3 text-[15px]">
          {busy ? `${t("in.filing")}…` : t("in.submit")}
        </button>
        <p className="text-center text-[12px] text-[var(--ink-soft)]">{t("in.privacy")}</p>
      </div>
    </div>
  );
}
