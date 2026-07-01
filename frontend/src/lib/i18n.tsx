/**
 * i18n - English is the source of truth (the EN map below). Every other language
 * is a JSON override file in ./locales/<code>.json, produced by the Sarvam
 * translation generator (server/scripts/gen_i18n.py). Any key missing from a
 * locale falls back to English, so the UI is always coherent.
 *
 * The language switcher lists every language Sarvam supports; picking one swaps
 * the entire interface.
 */
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

/** Every language Sarvam supports, with its native label and Sarvam STT/translate code. */
export const LANGUAGES = [
  { code: "en", sarvam: "en-IN", label: "English", native: "English" },
  { code: "hi", sarvam: "hi-IN", label: "Hindi", native: "हिन्दी" },
  { code: "mr", sarvam: "mr-IN", label: "Marathi", native: "मराठी" },
  { code: "bn", sarvam: "bn-IN", label: "Bengali", native: "বাংলা" },
  { code: "te", sarvam: "te-IN", label: "Telugu", native: "తెలుగు" },
  { code: "ta", sarvam: "ta-IN", label: "Tamil", native: "தமிழ்" },
  { code: "kn", sarvam: "kn-IN", label: "Kannada", native: "ಕನ್ನಡ" },
  { code: "gu", sarvam: "gu-IN", label: "Gujarati", native: "ગુજરાતી" },
  { code: "ml", sarvam: "ml-IN", label: "Malayalam", native: "മലയാളം" },
  { code: "pa", sarvam: "pa-IN", label: "Punjabi", native: "ਪੰਜਾਬੀ" },
  { code: "od", sarvam: "od-IN", label: "Odia", native: "ଓଡ଼ିଆ" },
] as const;

export type Lang = (typeof LANGUAGES)[number]["code"];

/** Sarvam language code for a UI language (used by intake STT/translate). */
export function sarvamCode(lang: Lang): string {
  return LANGUAGES.find((l) => l.code === lang)?.sarvam ?? "en-IN";
}

/** English source strings. Keep terse and operational - no marketing copy. */
export const EN: Record<string, string> = {
  // chrome
  "app.name": "NANDI",
  "app.tagline": "Missing Persons Reunification",
  "app.place": "Simhastha Kumbh Mela 2027 · Nashik–Trimbakeshwar",
  "nav.overview": "Dashboard",
  "nav.report": "Intake",
  "nav.operator": "Operator",
  "nav.blast": "Broadcast",
  "lang.label": "Language",

  // shared
  "s.live": "Live",
  "s.reconnecting": "Reconnecting",
  "s.captured": "records",
  "s.nameUnknown": "Name unknown",
  "s.loading": "Loading",
  "s.close": "Close",
  "s.missing": "Missing",
  "s.found": "Found",
  "s.foundPerson": "found",
  "s.all": "All",
  "s.none": "None",

  // dashboard
  "ov.title": "Operations dashboard",
  "ov.sub": "Live case status across all reporting centres.",
  "ov.total": "Total cases",
  "ov.live": "captured live",
  "ov.reunited": "Reunited",
  "ov.families": "families",
  "ov.avg": "Median resolution",
  "ov.avgSub": "report to handoff",
  "ov.dupes": "Duplicates caught",
  "ov.dupesSub": "same person, multiple centres",
  "ov.metrics": "Operational metrics",
  "ov.metricsHint": "open workload and risk",
  "m.cross": "Cross-centre matches",
  "m.crossD": "matched across reporting centres",
  "m.dupe": "Duplicate reports",
  "m.dupeD": "likely same person, filed twice",
  "m.noName": "Cases without a name",
  "m.noNameD": "still searchable by description",
  "m.noPhone": "Cases without a phone",
  "m.noPhoneD": "no reliable contact on file",
  "m.escal": "Needs escalation",
  "m.escalD": "open past the response window",
  "m.risk": "High-risk, unresolved",
  "m.riskD": "children and elders still open",
  "ov.perDay": "Reports per day",
  "ov.perDayHint": "by date filed",
  "ov.byAge": "Missing by age band",
  "ov.byAgeHint": "elders at highest risk",
  "ov.outcomes": "Case outcomes",
  "ov.languages": "Languages spoken",
  "ov.languagesHint": "native-language intake coverage",
  "ov.channels": "Intake channels",
  "ov.hotspots": "Last-seen hotspots",
  "ov.hotspotsHint": "where separations cluster",

  // intake
  "in.title": "Report a missing person",
  "in.sub": "No field is required. Tell us what you remember.",
  "in.speak": "Speak in your language",
  "in.stopSpeaking": "Stop recording",
  "in.speakHint": "Speak in any language. We fill the form for you.",
  "in.recording": "Recording. Tap to stop.",
  "in.transcribing": "Transcribing",
  "in.understanding": "Reading the details",
  "in.orType": "Or type in any language",
  "in.typePlaceholder": "e.g. my father is missing, 72 years, saffron kurta, near Ramkund",
  "in.autofill": "Autofill",
  "in.heard": "heard",
  "in.confidence": "confidence",
  "in.autofilled": "Fields below were filled automatically. Check and correct them.",
  "in.name": "Name (if known)",
  "in.namePlaceholder": "e.g. Ramesh Patil",
  "in.gender": "Gender",
  "in.male": "Male",
  "in.female": "Female",
  "in.unknown": "Unknown",
  "in.ageGroup": "Age group",
  "in.lastSeen": "Last seen where?",
  "in.lastSeenPlaceholder": "e.g. Ramkund ghat",
  "in.desc": "What were they wearing / what do they look like?",
  "in.descPlaceholder": "e.g. saffron kurta, white dhoti, rudraksha mala",
  "in.state": "Home state",
  "in.mobile": "Your mobile",
  "in.photo": "Photo (optional)",
  "in.photoAdd": "Add photo",
  "in.photoRemove": "Remove",
  "in.submit": "File report",
  "in.filing": "Filing",
  "in.privacy": "Your number is stored masked.",
  "in.filed": "Report filed",
  "in.filedSub": "Filed and searchable across all centres.",
  "in.caseId": "Case ID",
  "in.fileAnother": "File another",
  "in.type": "Report type",

  // operator
  "op.title": "Operator console",
  "op.sub": "Live case queue. Register a found person to rank candidate matches.",
  "op.booth": "Booth",
  "op.queue": "Queue",
  "op.registerFound": "Register found person",
  "op.newFound": "New found record",
  "op.descReq": "Description (clothes, appearance)",
  "op.nameKnown": "Name (if known)",
  "op.approxAge": "Approx. age",
  "op.language": "Language",
  "op.registerMatch": "Register & find matches",
  "op.searching": "Searching",
  "op.candidates": "Candidate matches",
  "op.searchingGraph": "Searching records and validating against the venue graph.",
  "op.confirmed": "Match confirmed",
  "op.reunionAt": "Handoff at",
  "op.otpTelegram": "Sent to the family on Telegram with this code.",
  "op.otpOnscreen": "Read this code aloud to the family.",
  "op.verifyCode": "Verification code",
  "op.reunitePrompt": "Family arrived? Enter the code they present.",
  "op.reuniteConfirm": "Mark reunited",
  "op.reuniteVerifying": "Verifying",
  "op.reuniteBadCode": "Incorrect or expired code.",
  "op.reunitedDone": "Reunited. Case closed.",
  "op.confidence": "confidence",
  "op.vector": "text",
  "op.confirm": "Confirm",
  "op.reject": "Reject",
  "op.rejectAll": "Reject all candidates",
  "op.noCandidates": "No candidates above the confidence floor. The found record stays unmatched and escalates on the normal timeline.",
  "op.findMatches": "Find matches",
  "op.blastZone": "Broadcast this zone",
  "op.blasting": "Sending",
  "op.blasted": "Alerted {n} recipients across {z} zones.",
  "op.missingHint": "Missing-person record, searchable on arrival. Register the matching found person to surface it as a candidate.",
  "op.age": "Age",
  "op.from": "From",
  "op.contact": "Contact",
  "op.description": "Description",
  "op.selectReport": "Select a case to see details.",
  "op.noChannel": "No records on this channel.",
  "op.status": "Status",
  "op.reportedAt": "Reported",
  "op.priority": "Priority",
  "op.priorityQueue": "{n} priority - children & elders",
  "op.priorityCase": "Vulnerable person - act first. Broadcast the zone immediately.",
  "op.voiceHint": "Describe using voice (Sarvam + Claude)",
  "op.voiceSpeak": "Tap to speak the description in any language",

  // broadcast
  "bl.eyebrow": "Escalation · zone broadcast",
  "bl.title": "Broadcast to a zone",
  "bl.sub": "Post once to a zone's public Telegram channel and reach every pilgrim who joined it - plus its neighbouring zones. Same engine as the 24h re-broadcast and 72h police escalation.",
  "bl.zoneChannels": "Zone channels",
  "bl.channelHint": "Pilgrims join a zone's channel by scanning the QR posted at its booths. One broadcast reaches every member.",
  "bl.setChannel": "Set",
  "bl.channelPlaceholder": "@channel or -100… chat id",
  "bl.join": "Join",
  "bl.noChannelSet": "No channel",
  "bl.members": "members",
  "bl.reach": "estimated reach",
  "bl.postedTo": "Posted to {n} zone channel(s)",
  "bl.emailRecipients": "Email recipients",
  "bl.emailHint": "Registered families and officials (direct email).",
  "bl.channels": "Channels",
  "bl.ready": "ready",
  "bl.noKeys": "no keys configured",
  "bl.live": "live",
  "bl.noKey": "no key",
  "bl.noKeyNote": "With no channel keys a broadcast still resolves every recipient and writes the audit trail - each send is logged instead of dispatched. Add a key to go live.",
  "bl.blastZone": "Compose broadcast",
  "bl.reachable": "reachable in this zone",
  "bl.targetZone": "Target zone",
  "bl.reachableShort": "reachable",
  "bl.adjacentNote": "Adjacent zones are included automatically.",
  "bl.subject": "Subject (email title)",
  "bl.message": "Message",
  "bl.messagePlaceholder": "e.g. a 7-year-old boy in a red t-shirt was found at Ramkund",
  "bl.send": "Broadcast",
  "bl.sending": "Sending",
  "bl.dispatched": "Broadcast sent",
  "bl.targeted": "Reached {n} recipients across {z} zones.",
  "bl.noRecipients": "No opted-in recipients in this zone. Add some on the right, then broadcast.",
  "bl.sentOf": "sent",
  "bl.subscribers": "Subscribers",
  "bl.total": "total",
  "bl.noZone": "No zone",
  "bl.addrEmail": "email address",
  "bl.addrTelegram": "telegram chat id",
  "bl.addrPhone": "phone (+91…)",
  "bl.nameOpt": "name (optional)",
  "bl.addSub": "Add subscriber",
  "bl.adding": "Adding",
  "bl.noSubs": "No subscribers yet. Add one above, or let people opt in via the Telegram bot.",
};

// Locale overrides, generated by server/scripts/gen_i18n.py. Auto-discovered:
// dropping a new locale JSON here makes it live with no code change.
const localeModules = import.meta.glob("./locales/*.json", { eager: true, import: "default" }) as Record<
  string,
  Record<string, string>
>;
const LOCALES: Partial<Record<Lang, Record<string, string>>> = {};
for (const [path, dict] of Object.entries(localeModules)) {
  const code = path.split("/").pop()!.replace(".json", "") as Lang;
  LOCALES[code] = dict;
}

type Ctx = { lang: Lang; setLang: (l: Lang) => void };
const LangCtx = createContext<Ctx>({ lang: "en", setLang: () => {} });

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => {
    const saved = localStorage.getItem("nandi_lang") as Lang | null;
    return saved && LANGUAGES.some((l) => l.code === saved) ? saved : "en";
  });
  useEffect(() => {
    localStorage.setItem("nandi_lang", lang);
    document.documentElement.lang = lang;
  }, [lang]);
  return <LangCtx.Provider value={{ lang, setLang }}>{children}</LangCtx.Provider>;
}

export function useLang() {
  return useContext(LangCtx);
}

/** t(key, vars?) bound to the current language, falling back to English. */
export function useT() {
  const { lang } = useLang();
  return (key: string, vars?: Record<string, string | number>) => {
    let s = (lang !== "en" && LOCALES[lang]?.[key]) || EN[key] || key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
    return s;
  };
}

export function LanguageSwitcher() {
  const { lang, setLang } = useLang();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = LANGUAGES.find((l) => l.code === lang) ?? LANGUAGES[0];

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-md border border-[var(--line)] bg-[var(--surface)] px-2.5 py-1.5 text-[13px] font-semibold text-[var(--ink)] hover:border-[var(--line-strong)]"
        title="Language"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="opacity-70">
          <circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18" />
        </svg>
        <span>{current.native}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="opacity-50">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      {open && (
        <ul
          role="listbox"
          className="absolute right-0 z-50 mt-1 max-h-80 w-48 overflow-auto rounded-lg border border-[var(--line)] bg-[var(--surface)] py-1 shadow-lg"
        >
          {LANGUAGES.map((l) => (
            <li key={l.code}>
              <button
                role="option"
                aria-selected={lang === l.code}
                onClick={() => { setLang(l.code); setOpen(false); }}
                className={`flex w-full items-center justify-between px-3 py-2 text-left text-[13px] hover:bg-[var(--surface-2)] ${
                  lang === l.code ? "font-bold text-[var(--accent)]" : "text-[var(--ink)]"
                }`}
              >
                <span>{l.native}</span>
                <span className="text-[11px] text-[var(--ink-soft)]">{l.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
