import { useEffect, useMemo, useState } from "react";
import { useFeed } from "../lib/useFeed";
import { ChannelBadge, StatusPill } from "../components/ui";
import { api, type Booth, type MatchCandidate, type ConfirmResult, type Report } from "../lib/api";
import { useT } from "../lib/i18n";

function timeAgo(iso: string) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

const FILTERS = ["all", "web", "telegram", "whatsapp", "booth"] as const;

const BAND: Record<string, { label: string; dot: string; bg: string }> = {
  high: { label: "High", dot: "var(--color-saffron)", bg: "rgba(224,133,43,0.08)" },
  probable: { label: "Probable", dot: "var(--color-saffron-deep)", bg: "rgba(224,133,43,0.05)" },
  possible: { label: "Possible", dot: "var(--color-ink-soft)", bg: "rgba(108,99,88,0.05)" },
};

const inputCls =
  "w-full rounded-xl border border-[var(--color-line)] bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[var(--color-saffron)]/30";

export default function Operator() {
  const t = useT();
  const { reports, connected, latestId } = useFeed(60);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const [sel, setSel] = useState<Report | null>(null);
  const [booth, setBooth] = useState<Booth | null>(null);

  // match flow
  const [matchFor, setMatchFor] = useState<{ foundId: string; label: string } | null>(null);
  const [candidates, setCandidates] = useState<MatchCandidate[] | null>(null);
  const [matching, setMatching] = useState(false);
  const [result, setResult] = useState<(ConfirmResult & { name: string }) | null>(null);

  // register-found form
  const [showReg, setShowReg] = useState(false);
  const [reg, setReg] = useState({ physical_description: "", name_if_known: "", approximate_age: "", gender: "", language_spoken: "" });
  const [regBusy, setRegBusy] = useState(false);

  // blast-this-zone
  const [blasting, setBlasting] = useState(false);
  const [blastMsg, setBlastMsg] = useState<string | null>(null);

  useEffect(() => { api.booths().then((b) => setBooth(b[0] ?? null)).catch(() => {}); }, []);
  useEffect(() => { setBlastMsg(null); }, [sel]);

  const shown = useMemo(
    () => (filter === "all" ? reports : reports.filter((r) => r.channel === filter)),
    [reports, filter]
  );
  const active = sel ?? shown[0] ?? null;

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
      setResult({ ...res, name: c.subject_name || "the family" });
      setCandidates(null);
    } catch (e) {
      alert("Confirm failed: " + (e as Error).message);
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
    setBlasting(true);
    setBlastMsg(null);
    try {
      const r = await api.blastFound(foundId);
      setBlastMsg(t("op.blasted", { n: r.targeted, z: r.zones.length }));
    } catch (e) {
      setBlastMsg("Blast failed: " + (e as Error).message);
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
      });
      setReg({ physical_description: "", name_if_known: "", approximate_age: "", gender: "", language_spoken: "" });
      setShowReg(false);
      await findMatches(res.found_id, res.case_id);
    } catch (e) {
      alert("Could not register: " + (e as Error).message);
    } finally {
      setRegBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div>
          <h2 className="text-xl font-extrabold">{t("op.title")}</h2>
          <p className="text-xs text-[var(--color-ink-soft)]">
            {t("op.sub")}
            {booth && <> · {t("op.booth")}: <b className="text-[var(--color-ink)]">{booth.name}</b></>}
          </p>
        </div>
        <span className="ml-auto inline-flex items-center gap-2 rounded-full border border-[var(--color-line)] bg-white px-3 py-1.5 text-xs font-semibold">
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-[var(--color-saffron)] animate-livepulse" : "bg-[var(--color-line-2)]"}`} />
          {connected ? t("s.live") : `${t("s.reconnecting")}…`}
          <span className="text-[var(--color-ink-soft)]">· {reports.length} {t("s.captured")}</span>
        </span>
      </div>

      {/* Register found person */}
      <div className="card p-4">
        <button onClick={() => setShowReg((v) => !v)} className="flex w-full items-center gap-2 text-left">
          <span className="grid h-7 w-7 place-items-center rounded-full nandi-gradient text-white">+</span>
          <span className="font-semibold">{t("op.registerFound")}</span>
          <span className="ml-auto text-xs text-[var(--color-ink-soft)]">{showReg ? "▲" : "▼"}</span>
        </button>
        {showReg && (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <textarea className={inputCls + " sm:col-span-2"} rows={2} placeholder={t("op.descReq")}
              value={reg.physical_description} onChange={(e) => setReg({ ...reg, physical_description: e.target.value })} />
            <input className={inputCls} placeholder={t("op.nameKnown")} value={reg.name_if_known} onChange={(e) => setReg({ ...reg, name_if_known: e.target.value })} />
            <input className={inputCls} type="number" placeholder={t("op.approxAge")} value={reg.approximate_age} onChange={(e) => setReg({ ...reg, approximate_age: e.target.value })} />
            <select className={inputCls} value={reg.gender} onChange={(e) => setReg({ ...reg, gender: e.target.value })}>
              <option value="">{t("in.gender")}</option><option value="male">{t("in.male")}</option><option value="female">{t("in.female")}</option><option value="unknown">{t("in.unknown")}</option>
            </select>
            <input className={inputCls} placeholder={t("op.language")} value={reg.language_spoken} onChange={(e) => setReg({ ...reg, language_spoken: e.target.value })} />
            <button onClick={registerFound} disabled={regBusy || !reg.physical_description.trim()}
              className="nandi-gradient rounded-xl py-2.5 font-semibold text-white disabled:opacity-60 sm:col-span-2">
              {regBusy ? `${t("op.searching")}…` : t("op.registerMatch")}
            </button>
          </div>
        )}
      </div>

      {/* Match results panel */}
      {matchFor && (
        <div className="card border-2 border-[var(--color-saffron)]/20 p-5">
          <div className="flex items-center gap-2">
            <span className="font-bold">{t("op.candidates")} {matchFor.label}</span>
            <button onClick={() => { setMatchFor(null); setCandidates(null); setResult(null); }} className="ml-auto text-xs text-[var(--color-ink-soft)]">✕ {t("s.close")}</button>
          </div>

          {matching && <div className="mt-4 text-sm text-[var(--color-ink-soft)] animate-livepulse">{t("op.searchingGraph")}</div>}

          {result && (
            <div className="mt-4 rounded-xl border border-[var(--color-saffron)]/30 bg-[rgba(224,133,43,0.07)] p-4">
              <div className="font-bold text-[var(--color-saffron-deep)]">✓ {t("op.confirmed")}</div>
              <p className="mt-1 text-sm">
                {t("op.reunionAt")} <b>{result.booth_name || t("op.booth")}</b>{result.zone_name && <> ({result.zone_name})</>}.{" "}
                {result.otp_dispatched ? t("op.otpSent") : t("op.otpNoKey")}
              </p>
            </div>
          )}

          {candidates && candidates.length > 0 && (
            <div className="mt-4 space-y-3">
              {candidates.map((c) => {
                const b = BAND[c.band] ?? BAND.possible;
                return (
                  <div key={c.missing_id} className="rounded-xl border border-[var(--color-line)] p-4" style={{ background: b.bg }}>
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-2.5 py-1 text-[11px] font-bold" style={{ border: "1px solid var(--color-line)" }}>
                        <span className="h-1.5 w-1.5 rounded-full" style={{ background: b.dot }} />{b.label}
                      </span>
                      <span className="text-sm font-bold">{Math.round(c.confidence * 100)}% {t("op.confidence")}</span>
                      <span className="text-xs text-[var(--color-ink-soft)]">{t("op.vector")} {Math.round(c.vector_score * 100)}%</span>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-base font-bold">{c.subject_name || t("s.nameUnknown")}</span>
                      <span className="text-sm text-[var(--color-ink-soft)]">{[c.subject_gender, c.subject_age ? `${c.subject_age}y` : null, c.origin_city].filter(Boolean).join(" · ")}</span>
                    </div>
                    <p className="mt-1 text-sm text-[var(--color-ink-soft)]">{c.physical_description}</p>
                    {c.reasons.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {c.reasons.map((r, i) => (
                          <span key={i} className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium" style={{ border: "1px solid var(--color-line)" }}>{r}</span>
                        ))}
                      </div>
                    )}
                    <div className="mt-3 flex gap-2">
                      <button onClick={() => confirm(c)} className="btn-dark px-4 py-2 text-sm">✓ {t("op.confirm")}</button>
                    </div>
                  </div>
                );
              })}
              <button onClick={reject} className="btn-ghost px-4 py-2 text-sm">{t("op.rejectAll")}</button>
            </div>
          )}

          {candidates && candidates.length === 0 && !matching && (
            <div className="mt-4 text-sm text-[var(--color-ink-soft)]">{t("op.noCandidates")}</div>
          )}
        </div>
      )}

      <div className="flex gap-1.5">
        {FILTERS.map((f) => (
          <button key={f} onClick={() => setFilter(f)}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold capitalize transition ${
              filter === f ? "bg-[var(--color-ink)] text-white" : "bg-white text-[var(--color-ink-soft)] border border-[var(--color-line)]"
            }`}>
            {f}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        {/* Feed */}
        <div className="space-y-2.5">
          {shown.map((r) => (
            <button key={r.id} onClick={() => setSel(r)}
              className={`card w-full p-4 text-left transition hover:shadow-md ${
                r.id === latestId ? "animate-rise ring-2 ring-[var(--color-saffron)]/40" : ""
              } ${active?.id === r.id ? "ring-2 ring-[var(--color-saffron)]/30" : ""}`}>
              <div className="flex items-center gap-2">
                <ChannelBadge channel={r.channel} />
                <StatusPill status={r.status} />
                {r.report_type === "found" && <span className="text-[11px] font-semibold text-[var(--color-saffron-deep)]">{t("s.foundPerson")}</span>}
                <span className="ml-auto text-[11px] text-[var(--color-ink-soft)]">{timeAgo(r.reported_at)}</span>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-base font-bold">{r.person_name || t("s.nameUnknown")}</span>
                <span className="text-xs text-[var(--color-ink-soft)]">{r.case_id}</span>
              </div>
              <div className="mt-0.5 text-sm text-[var(--color-ink-soft)]">
                {[r.gender, r.age_band, r.language].filter(Boolean).join(" · ")}
                {r.last_seen_location && <> · {t("in.lastSeen")} <b className="text-[var(--color-ink)]">{r.last_seen_location}</b></>}
              </div>
            </button>
          ))}
          {shown.length === 0 && (
            <div className="card p-8 text-center text-sm text-[var(--color-ink-soft)]">{t("op.noChannel")}</div>
          )}
        </div>

        {/* Detail */}
        <div className="lg:sticky lg:top-20 lg:self-start">
          {active ? (
            <div className="card p-5">
              <div className="flex items-center gap-2">
                <ChannelBadge channel={active.channel} />
                <StatusPill status={active.status} />
              </div>
              <h3 className="mt-3 text-lg font-extrabold">{active.person_name || t("s.nameUnknown")}</h3>
              <div className="text-xs text-[var(--color-ink-soft)]">{active.case_id}</div>

              <dl className="mt-4 space-y-2 text-sm">
                {([
                  [t("op.age"), active.age_band],
                  [t("in.gender"), active.gender],
                  [t("op.language"), active.language],
                  [t("in.lastSeen"), active.last_seen_location],
                  [t("op.from"), [active.district, active.state].filter(Boolean).join(", ")],
                  [t("op.contact"), active.reporter_mobile_masked],
                ] as [string, string | null][]).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3 border-b border-dashed border-[var(--color-line)] pb-2">
                    <dt className="text-[var(--color-ink-soft)]">{k}</dt>
                    <dd className="text-right font-semibold">{v || "-"}</dd>
                  </div>
                ))}
              </dl>

              {active.physical_description && (
                <div className="mt-4">
                  <div className="text-xs font-bold uppercase tracking-wide text-[var(--color-ink-soft)]">{t("op.description")}</div>
                  <p className="mt-1 rounded-xl bg-[var(--color-paper-2)] p-3 text-sm">{active.physical_description}</p>
                </div>
              )}

              {active.report_type === "found" ? (
                <div className="mt-4 space-y-2">
                  <button onClick={() => findMatches(active.id, active.case_id)} disabled={!booth}
                    className="nandi-gradient w-full rounded-xl py-3 font-bold text-white disabled:opacity-60">
                    {t("op.findMatches")}
                  </button>
                  <button onClick={() => blastThisZone(active.id)} disabled={blasting}
                    className="btn-ghost w-full py-2.5 text-sm disabled:opacity-60">
                    {blasting ? `${t("op.blasting")}…` : t("op.blastZone")}
                  </button>
                  {blastMsg && (
                    <p className="rounded-xl border border-[var(--color-line)] bg-[var(--color-bg-soft)] p-2.5 text-xs text-[var(--color-ink-soft)]">{blastMsg}</p>
                  )}
                </div>
              ) : (
                <p className="mt-4 rounded-xl border border-[var(--color-line)] bg-[var(--color-bg-soft)] p-3 text-xs text-[var(--color-ink-soft)]">
                  {t("op.missingHint")}
                </p>
              )}
            </div>
          ) : (
            <div className="card p-8 text-center text-sm text-[var(--color-ink-soft)]">{t("op.selectReport")}</div>
          )}
        </div>
      </div>
    </div>
  );
}
