import { useEffect, useMemo, useState } from "react";
import { useFeed } from "../lib/useFeed";
import { ChannelBadge, StatusPill, statusTone } from "../components/ui";
import { api, type Booth, type MatchCandidate, type ConfirmResult, type Report } from "../lib/api";
import { useT, LANGUAGES } from "../lib/i18n";
import { useRecorder } from "../lib/useRecorder";

function timeAgo(iso: string) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

const TONE_DOT: Record<string, string> = {
  active: "var(--warn)", matched: "var(--info)", reunited: "var(--ok)", risk: "var(--danger)", closed: "var(--ink-faint)",
};

const FILTERS = ["all", "web", "telegram", "booth"] as const;

const BAND: Record<string, { label: string; fg: string; bg: string }> = {
  high: { label: "High", fg: "var(--ok)", bg: "var(--ok-soft)" },
  probable: { label: "Probable", fg: "var(--info)", bg: "var(--info-soft)" },
  possible: { label: "Possible", fg: "var(--ink-soft)", bg: "var(--surface-2)" },
};

function Mic({ on }: { on: boolean }) {
  return on ? <span className="block h-2.5 w-2.5 rounded-[2px] bg-white" /> : (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  );
}
function Camera() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 8a2 2 0 0 1 2-2h2l1.5-2h7L19 6h0a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><circle cx="12" cy="12.5" r="3.2" />
    </svg>
  );
}

export default function Operator() {
  const t = useT();
  const { reports, connected, latestId } = useFeed(60);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const [sel, setSel] = useState<Report | null>(null);
  const [booth, setBooth] = useState<Booth | null>(null);
  const [query, setQuery] = useState("");

  // match flow
  const [matchFor, setMatchFor] = useState<{ foundId: string; label: string } | null>(null);
  const [candidates, setCandidates] = useState<MatchCandidate[] | null>(null);
  const [matching, setMatching] = useState(false);
  const [result, setResult] = useState<(ConfirmResult & { name: string; missing_id: string }) | null>(null);
  const [otpInput, setOtpInput] = useState("");
  const [reunited, setReunited] = useState(false);
  const [reuniteBusy, setReuniteBusy] = useState(false);
  const [reuniteErr, setReuniteErr] = useState<string | null>(null);

  // register-found form
  const [showReg, setShowReg] = useState(false);
  const [reg, setReg] = useState({ physical_description: "", name_if_known: "", approximate_age: "", gender: "", language_spoken: "", photo_url: "" });
  const [regBusy, setRegBusy] = useState(false);

  const rec = useRecorder();
  const [voiceStage, setVoiceStage] = useState<"" | "transcribing" | "thinking" | "done">("");

  // blast-this-zone
  const [blasting, setBlasting] = useState(false);
  const [blastMsg, setBlastMsg] = useState<string | null>(null);

  useEffect(() => { api.booths().then((b) => setBooth(b[0] ?? null)).catch(() => {}); }, []);
  useEffect(() => { setBlastMsg(null); }, [sel]);

  const shown = useMemo(() => {
    let list = filter === "all" ? reports : reports.filter((r) => r.channel === filter);
    const q = query.trim().toLowerCase();
    if (q) list = list.filter((r) =>
      [r.person_name, r.case_id, r.last_seen_location, r.physical_description].filter(Boolean).join(" ").toLowerCase().includes(q));
    // Vulnerable-person cases jump the queue (stable sort keeps recency within a tier).
    return [...list].sort((a, b) => Number(!!b.priority) - Number(!!a.priority));
  }, [reports, filter, query]);
  const active = sel ?? shown[0] ?? null;
  const priorityCount = useMemo(() => reports.filter((r) => r.priority).length, [reports]);

  function applyExtracted(ex: any) {
    if (ex.confidence < 0.15) {
      alert("Could not extract details. Describe the person's name, age, clothing, or where they were last seen.");
      return;
    }
    setReg((p) => ({
      ...p,
      physical_description: ex.physical_description || p.physical_description,
      name_if_known: ex.person_name || p.name_if_known,
      approximate_age: ex.age_years ? String(ex.age_years) : p.approximate_age,
      gender: ex.gender ? ex.gender.toLowerCase() : p.gender,
      language_spoken: ex.language || p.language_spoken,
    }));
  }

  async function onMic() {
    if (rec.recording) {
      const blob = await rec.stop();
      try {
        setVoiceStage("transcribing");
        const tr = await api.transcribe(blob);
        setVoiceStage("thinking");
        const ex = await api.extract(tr.transcript, tr.language_code);
        applyExtracted(ex);
        setVoiceStage("done");
      } catch (e) {
        alert("Voice processing failed: " + (e as Error).message);
        setVoiceStage("");
      }
    } else {
      setVoiceStage("");
      rec.start();
    }
  }

  async function findMatches(foundId: string, label: string) {
    setMatchFor({ foundId, label });
    setResult(null);
    setCandidates(null);
    setMatching(true);
    try {
      const r = await api.match(foundId);
      setCandidates(r.candidates);
    } catch (e) {
      alert("Match lookup failed: " + (e as Error).message);
    } finally {
      setMatching(false);
    }
  }

  async function confirm(c: MatchCandidate) {
    if (!matchFor || !booth) return;
    try {
      const res = await api.matchConfirm(matchFor.foundId, c.missing_id, booth.id, "operator-console");
      setResult({ ...res, name: c.subject_name || "the family", missing_id: c.missing_id });
      setOtpInput(""); setReunited(false); setReuniteErr(null); setCandidates(null);
    } catch (e) {
      alert("Confirm failed: " + (e as Error).message);
    }
  }

  async function reunite() {
    if (!matchFor || !booth || !result) return;
    setReuniteBusy(true); setReuniteErr(null);
    try {
      const res = await api.matchReunite(matchFor.foundId, result.missing_id, booth.id, otpInput.trim(), "operator-console");
      if (res.reunited) setReunited(true);
      else setReuniteErr(res.detail || t("op.reuniteBadCode"));
    } catch (e) {
      setReuniteErr("Reunite failed: " + (e as Error).message);
    } finally {
      setReuniteBusy(false);
    }
  }

  async function reject() {
    if (!matchFor || !booth || !candidates) return;
    try {
      await api.matchReject(matchFor.foundId, booth.id, candidates.map((c) => c.missing_id), "operator-console");
      setCandidates([]);
    } catch (e) {
      alert("Reject failed: " + (e as Error).message);
    }
  }

  async function blastThisZone(foundId: string) {
    setBlasting(true); setBlastMsg(null);
    try {
      const r = await api.blastFound(foundId);
      setBlastMsg(t("op.blasted", { n: r.targeted, z: r.zones.length }));
    } catch (e) {
      setBlastMsg("Broadcast failed: " + (e as Error).message);
    } finally {
      setBlasting(false);
    }
  }

  async function registerFound() {
    if (!reg.physical_description.trim()) return;
    setRegBusy(true);
    try {
      const res = await api.fileFound({
        physical_description: reg.physical_description,
        name_if_known: reg.name_if_known || null,
        approximate_age: reg.approximate_age ? Number(reg.approximate_age) : null,
        gender: reg.gender || null,
        language_spoken: reg.language_spoken || null,
        registered_at_booth: booth?.id ?? null,
        photo_url: reg.photo_url || null,
      });
      setReg({ physical_description: "", name_if_known: "", approximate_age: "", gender: "", language_spoken: "", photo_url: "" });
      setShowReg(false);
      await findMatches(res.found_id, res.case_id);
    } catch (e) {
      alert("Could not register: " + (e as Error).message);
    } finally {
      setRegBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      {/* Command strip */}
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="text-[17px] font-extrabold tracking-tight">{t("op.title")}</h1>
          <p className="text-[12px] text-[var(--ink-soft)]">
            {booth ? <>{t("op.booth")}: <b className="text-[var(--ink)]">{booth.name}</b></> : t("op.sub")}
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
          {priorityCount > 0 && (
            <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border border-[var(--danger)] bg-[var(--danger-soft)] px-2.5 py-1.5 text-[12px] font-bold text-[var(--danger)]">
              <span className="h-2 w-2 shrink-0 rounded-full bg-[var(--danger)] animate-livepulse" />
              {t("op.priorityQueue", { n: priorityCount })}
            </span>
          )}
          <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border border-[var(--line)] bg-[var(--surface)] px-2.5 py-1.5 text-[12px] font-semibold">
            <span className={`h-2 w-2 shrink-0 rounded-full ${connected ? "bg-[var(--ok)] animate-livepulse" : "bg-[var(--line-2)]"}`} />
            {connected ? t("s.live") : `${t("s.reconnecting")}…`}
            <span className="mono text-[var(--ink-soft)]">{reports.length}</span>
          </span>
          <button onClick={() => setShowReg(true)} className="btn btn-primary">
            <span className="text-[15px] leading-none">+</span> {t("op.registerFound")}
          </button>
        </div>
      </div>

      {/* Control panel: queue + workspace */}
      <div className="grid gap-3 lg:grid-cols-[minmax(300px,360px)_1fr]">
        {/* Queue */}
        <div className="panel flex max-h-[52vh] flex-col overflow-hidden lg:max-h-[calc(100vh-140px)]">
          <div className="border-b border-[var(--line)] p-2">
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name, ID, location…" className="field py-1.5 text-[13px]" />
            <div className="mt-2 flex gap-1">
              {FILTERS.map((f) => (
                <button key={f} onClick={() => setFilter(f)}
                  className={`rounded px-2 py-1 text-[11px] font-bold uppercase tracking-wide transition ${
                    filter === f ? "bg-[var(--ink)] text-white" : "text-[var(--ink-soft)] hover:bg-[var(--surface-2)]"
                  }`}>
                  {f === "all" ? t("s.all") : f}
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1 divide-y divide-[var(--line)] overflow-y-auto">
            {shown.map((r) => (
              <button key={r.id} onClick={() => { setSel(r); setMatchFor(null); }}
                className={`block w-full px-3 py-2 text-left transition ${
                  active?.id === r.id ? "bg-[var(--accent-soft)]" : "hover:bg-[var(--surface-2)]"
                } ${r.id === latestId ? "animate-rise" : ""}`}>
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: r.priority ? "var(--danger)" : TONE_DOT[statusTone(r.status)] }} />
                  <span className="truncate text-[13px] font-bold">{r.person_name || t("s.nameUnknown")}</span>
                  {r.priority && <span className="rounded bg-[var(--danger-soft)] px-1 text-[9.5px] font-bold uppercase text-[var(--danger)]">{t("op.priority")}</span>}
                  {r.report_type === "found" && <span className="rounded bg-[var(--info-soft)] px-1 text-[9.5px] font-bold uppercase text-[var(--info)]">F</span>}
                  <span className="mono ml-auto shrink-0 text-[10px] text-[var(--ink-faint)]">{timeAgo(r.reported_at)}</span>
                </div>
                <div className="mt-0.5 flex items-center gap-1.5 pl-4">
                  <span className="mono text-[10.5px] text-[var(--ink-soft)]">{r.case_id}</span>
                  <span className="truncate text-[11px] text-[var(--ink-soft)]">
                    {[r.gender?.[0], r.age_band, r.language].filter(Boolean).join(" · ")}
                  </span>
                </div>
              </button>
            ))}
            {shown.length === 0 && <div className="p-6 text-center text-[13px] text-[var(--ink-soft)]">{t("op.noChannel")}</div>}
          </div>
        </div>

        {/* Workspace */}
        <div className="min-w-0">
          {matchFor ? (
            <MatchWorkspace
              t={t} label={matchFor.label} matching={matching} candidates={candidates} result={result}
              reunited={reunited} otpInput={otpInput} setOtpInput={setOtpInput} reuniteBusy={reuniteBusy} reuniteErr={reuniteErr}
              onClose={() => { setMatchFor(null); setCandidates(null); setResult(null); }}
              onConfirm={confirm} onReject={reject} onReunite={reunite}
            />
          ) : active ? (
            <CaseDetail
              t={t} r={active} booth={booth} blasting={blasting} blastMsg={blastMsg}
              onFind={() => findMatches(active.id, active.case_id)} onBlast={() => blastThisZone(active.id)}
            />
          ) : (
            <div className="panel grid h-64 place-items-center text-[13px] text-[var(--ink-soft)]">{t("op.selectReport")}</div>
          )}
        </div>
      </div>

      {showReg && (
        <RegisterFound
          t={t} reg={reg} setReg={setReg} regBusy={regBusy} rec={rec} voiceStage={voiceStage} onMic={onMic}
          onClose={() => setShowReg(false)} onSubmit={registerFound}
        />
      )}
    </div>
  );
}

// ── Case detail ──────────────────────────────────────────────────────────────
function CaseDetail({ t, r, booth, blasting, blastMsg, onFind, onBlast }: any) {
  const rows: [string, string | null][] = [
    [t("op.age"), r.age_band], [t("in.gender"), r.gender], [t("op.language"), r.language],
    [t("in.lastSeen"), r.last_seen_location], [t("op.from"), [r.district, r.state].filter(Boolean).join(", ")],
    [t("op.contact"), r.reporter_mobile_masked],
  ];
  return (
    <div className="panel p-4">
      <div className="flex items-start gap-3">
        {r.photo_url && (
          <img src={r.photo_url} alt="" onError={(e: any) => { e.currentTarget.style.display = "none"; }}
            className="h-16 w-16 shrink-0 rounded-md border border-[var(--line)] object-cover" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={r.status} />
            <ChannelBadge channel={r.channel} />
            <span className="rounded bg-[var(--surface-2)] px-1.5 py-0.5 text-[10.5px] font-bold uppercase text-[var(--ink-soft)]">
              {r.report_type === "found" ? t("s.found") : t("s.missing")}
            </span>
          </div>
          <h2 className="mt-1.5 text-[18px] font-extrabold leading-tight">{r.person_name || t("s.nameUnknown")}</h2>
          <div className="mono text-[12px] text-[var(--ink-soft)]">{r.case_id}</div>
        </div>
      </div>

      {r.priority && (
        <div className="mt-2 flex items-center gap-2 rounded-md border border-[var(--danger)] bg-[var(--danger-soft)] px-2.5 py-1.5 text-[12px] font-bold text-[var(--danger)]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>
          {t("op.priorityCase")}
        </div>
      )}

      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-0 sm:grid-cols-3">
        {rows.map(([k, v]) => (
          <div key={k} className="border-b border-dashed border-[var(--line)] py-1.5">
            <dt className="text-[10.5px] font-semibold uppercase tracking-wide text-[var(--ink-faint)]">{k}</dt>
            <dd className="text-[13px] font-semibold">{v || "-"}</dd>
          </div>
        ))}
      </dl>

      {r.physical_description && (
        <div className="mt-3">
          <div className="text-[10.5px] font-bold uppercase tracking-wide text-[var(--ink-faint)]">{t("op.description")}</div>
          <p className="mt-1 whitespace-pre-line rounded-md bg-[var(--surface-2)] p-2.5 text-[13px]">{r.physical_description}</p>
        </div>
      )}

      {r.report_type === "found" ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <button onClick={onFind} disabled={!booth} className="btn btn-primary">{t("op.findMatches")}</button>
          <button onClick={onBlast} disabled={blasting} className="btn btn-ghost">
            {blasting ? `${t("op.blasting")}…` : t("op.blastZone")}
          </button>
          {blastMsg && <p className="w-full rounded-md border border-[var(--line)] bg-[var(--surface-2)] p-2 text-[12px] text-[var(--ink-soft)]">{blastMsg}</p>}
        </div>
      ) : (
        <p className="mt-4 rounded-md border border-[var(--line)] bg-[var(--surface-2)] p-2.5 text-[12px] text-[var(--ink-soft)]">{t("op.missingHint")}</p>
      )}
    </div>
  );
}

// ── Match workspace ──────────────────────────────────────────────────────────
function MatchWorkspace({ t, label, matching, candidates, result, reunited, otpInput, setOtpInput, reuniteBusy, reuniteErr, onClose, onConfirm, onReject, onReunite }: any) {
  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2">
        <h2 className="text-[15px] font-extrabold">{t("op.candidates")}</h2>
        <span className="mono text-[12px] text-[var(--ink-soft)]">{label}</span>
        <button onClick={onClose} className="ml-auto text-[12px] font-semibold text-[var(--ink-soft)] hover:text-[var(--ink)]">✕ {t("s.close")}</button>
      </div>

      {matching && <div className="mt-4 text-[13px] text-[var(--ink-soft)] animate-livepulse">{t("op.searchingGraph")}</div>}

      {result && (
        <div className="mt-3 rounded-md border border-[var(--ok)] bg-[var(--ok-soft)] p-3">
          <div className="flex items-center gap-2 text-[13px] font-bold text-[var(--ok)]">✓ {t("op.confirmed")}</div>
          <p className="mt-1 text-[13px]">
            {t("op.reunionAt")} <b>{result.booth_name || t("op.booth")}</b>{result.zone_name && <> ({result.zone_name})</>}. {" "}
            {result.notify_channel === "telegram" && result.notified ? t("op.otpTelegram") : t("op.otpOnscreen")}
          </p>
          <div className="mt-2.5 flex items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--ink-faint)]">{t("op.verifyCode")}</span>
            <span className="mono rounded-md border border-[var(--line)] bg-[var(--surface)] px-3 py-1 text-[18px] font-bold tracking-[0.3em]">{result.otp}</span>
          </div>
          {reunited ? (
            <div className="mt-3 rounded-md bg-[var(--ok)] px-3 py-2 text-[13px] font-bold text-white">{t("op.reunitedDone")}</div>
          ) : (
            <div className="mt-3 border-t border-[var(--ok)]/30 pt-3">
              <div className="text-[12px] font-semibold text-[var(--ink-soft)]">{t("op.reunitePrompt")}</div>
              <div className="mt-1.5 flex items-center gap-2">
                <input value={otpInput} onChange={(e: any) => setOtpInput(e.target.value)} inputMode="numeric" placeholder="••••"
                  className="field mono w-24 py-1.5 text-center text-[15px] tracking-[0.25em]" />
                <button onClick={onReunite} disabled={reuniteBusy || otpInput.trim().length === 0} className="btn btn-ok">
                  {reuniteBusy ? `${t("op.reuniteVerifying")}…` : t("op.reuniteConfirm")}
                </button>
              </div>
              {reuniteErr && <div className="mt-1.5 text-[12px] text-[var(--danger)]">{reuniteErr}</div>}
            </div>
          )}
        </div>
      )}

      {candidates && candidates.length > 0 && !result && (
        <div className="mt-3 space-y-2">
          {candidates.map((c: MatchCandidate) => {
            const b = BAND[c.band] ?? BAND.possible;
            return (
              <div key={c.missing_id} className="rounded-md border border-[var(--line)] p-3">
                <div className="flex items-start gap-3">
                  {c.photo_url && (
                    <img src={c.photo_url} alt="" onError={(e: any) => { e.currentTarget.style.display = "none"; }}
                      className="h-14 w-14 shrink-0 rounded-md border border-[var(--line)] object-cover" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="pill" style={{ color: b.fg, background: b.bg }}>{b.label}</span>
                      <span className="mono text-[13px] font-bold">{Math.round(c.confidence * 100)}%</span>
                      <span className="text-[11px] text-[var(--ink-soft)]">{t("op.vector")} {Math.round(c.vector_score * 100)}%</span>
                    </div>
                    <div className="mt-1 flex items-baseline gap-2">
                      <span className="text-[14px] font-bold">{c.subject_name || t("s.nameUnknown")}</span>
                      <span className="text-[12px] text-[var(--ink-soft)]">{[c.subject_gender, c.subject_age ? `${c.subject_age}y` : null, c.origin_city].filter(Boolean).join(" · ")}</span>
                    </div>
                    <p className="mt-0.5 text-[12.5px] text-[var(--ink-soft)]">{c.physical_description}</p>
                    {c.reasons.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {c.reasons.map((r: string, i: number) => (
                          <span key={i} className="rounded bg-[var(--surface-2)] px-1.5 py-0.5 text-[10.5px] font-medium text-[var(--ink-soft)]">{r}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  <button onClick={() => onConfirm(c)} className="btn btn-ink self-center">✓ {t("op.confirm")}</button>
                </div>
              </div>
            );
          })}
          <button onClick={onReject} className="btn btn-danger">{t("op.rejectAll")}</button>
        </div>
      )}

      {candidates && candidates.length === 0 && !matching && (
        <div className="mt-3 rounded-md border border-[var(--line)] bg-[var(--surface-2)] p-3 text-[13px] text-[var(--ink-soft)]">{t("op.noCandidates")}</div>
      )}
    </div>
  );
}

// ── Register found (modal) ───────────────────────────────────────────────────
function RegisterFound({ t, reg, setReg, regBusy, rec, voiceStage, onMic, onClose, onSubmit }: any) {
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/30 p-4 sm:p-8" onClick={onClose}>
      <div className="panel w-full max-w-lg p-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2">
          <h2 className="text-[15px] font-extrabold">{t("op.newFound")}</h2>
          <button onClick={onClose} className="ml-auto text-[13px] font-semibold text-[var(--ink-soft)] hover:text-[var(--ink)]">✕</button>
        </div>

        {/* Voice capture */}
        <div className="mt-3 flex items-center gap-3 rounded-md border border-[var(--line)] bg-[var(--surface-2)] p-2.5">
          <button type="button" onClick={onMic}
            className={`grid h-9 w-9 shrink-0 place-items-center rounded-md text-white ${rec.recording ? "bg-[var(--danger)] animate-halo" : "bg-[var(--accent)]"}`}>
            <Mic on={rec.recording} />
          </button>
          <div className="text-[12px] leading-tight">
            <div className="font-bold">{rec.recording ? t("in.stopSpeaking") : t("op.voiceHint")}</div>
            <div className="text-[var(--ink-soft)]">{rec.recording ? t("in.recording") : t("op.voiceSpeak")}</div>
            {voiceStage && voiceStage !== "done" && (
              <div className="font-semibold text-[var(--accent-ink)] animate-livepulse">
                {voiceStage === "transcribing" ? `${t("in.transcribing")}…` : `${t("in.understanding")}…`}
              </div>
            )}
          </div>
        </div>

        <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
          <textarea className="field sm:col-span-2" rows={2} placeholder={t("op.descReq")}
            value={reg.physical_description} onChange={(e) => setReg({ ...reg, physical_description: e.target.value })} />
          <input className="field" placeholder={t("op.nameKnown")} value={reg.name_if_known} onChange={(e) => setReg({ ...reg, name_if_known: e.target.value })} />
          <input className="field" type="number" placeholder={t("op.approxAge")} value={reg.approximate_age} onChange={(e) => setReg({ ...reg, approximate_age: e.target.value })} />
          <select className="field" value={reg.gender} onChange={(e) => setReg({ ...reg, gender: e.target.value })}>
            <option value="">{t("in.gender")}</option>
            <option value="male">{t("in.male")}</option>
            <option value="female">{t("in.female")}</option>
            <option value="unknown">{t("in.unknown")}</option>
          </select>
          <select className="field" value={reg.language_spoken} onChange={(e) => setReg({ ...reg, language_spoken: e.target.value })}>
            <option value="">{t("op.language")}</option>
            {LANGUAGES.map((l) => <option key={l.code} value={l.label}>{l.native} · {l.label}</option>)}
          </select>

          {/* Photo */}
          <div className="sm:col-span-2 flex items-center gap-2.5 border-t border-[var(--line)] pt-2.5">
            <input type="file" accept="image/*" capture="environment" className="hidden" id="op-photo"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                try {
                  const res = await api.uploadPhoto(file);
                  setReg((r: any) => ({
                    ...r, photo_url: res.photo_url,
                    physical_description: r.physical_description ? `${r.physical_description}\n[photo] ${res.description}` : res.description || "",
                  }));
                } catch (err) { alert("Upload failed: " + (err as Error).message); }
              }} />
            <label htmlFor="op-photo" className="btn btn-ghost"><Camera /> {t("in.photoAdd")}</label>
            {reg.photo_url && (
              <>
                <img src={reg.photo_url} alt="" onError={(e: any) => { e.currentTarget.style.display = "none"; }} className="h-9 w-9 rounded-md border border-[var(--line)] object-cover" />
                <button type="button" onClick={() => setReg((r: any) => ({ ...r, photo_url: "" }))} className="text-[11px] font-semibold text-[var(--danger)]">{t("in.photoRemove")}</button>
              </>
            )}
          </div>

          <button onClick={onSubmit} disabled={regBusy || !reg.physical_description.trim()} className="btn btn-primary sm:col-span-2 py-2.5">
            {regBusy ? `${t("op.searching")}…` : t("op.registerMatch")}
          </button>
        </div>
      </div>
    </div>
  );
}
