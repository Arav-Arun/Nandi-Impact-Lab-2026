import { useEffect, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { api, type Stats } from "../lib/api";
import { SectionTitle, StatCard } from "../components/ui";
import { useT } from "../lib/i18n";

const ACCENT = "#d97a1f";
const INK = "#14161a";
const GRID = "#e6e9ec";
const AXIS = "#949ba4";
const OK = "#1f9d57";
const WARN = "#c9820f";
const INFO = "#2f6fd0";
const DANGER = "#d5432f";
const GRAY = "#c4cad1";
const tip = { borderRadius: 6, border: "1px solid #dce0e5", fontSize: 12, fontFamily: "JetBrains Mono, monospace" };

function toneColor(name: string): string {
  const s = name.toLowerCase();
  if (s.includes("reunit") || s.includes("resolv")) return OK;
  if (s.includes("match") || s.includes("pickup")) return INFO;
  if (s.includes("unresolv") || s.includes("escalat") || s.includes("risk")) return DANGER;
  if (s.includes("pending") || s.includes("active")) return WARN;
  return GRAY;
}

function pairs(rec: Record<string, number>) {
  return Object.entries(rec).map(([name, value]) => ({ name, value }));
}

function Metric({ value, label, desc, attention }: { value: number; label: string; desc: string; attention?: boolean }) {
  const alert = attention && value > 0;
  return (
    <div className="panel px-3 py-2.5" style={alert ? { borderColor: DANGER, background: "var(--danger-soft)" } : undefined}>
      <div className="mono text-[24px] font-bold leading-none" style={{ color: alert ? DANGER : INK }}>{value}</div>
      <div className="mt-1 text-[12.5px] font-bold">{label}</div>
      <div className="text-[11.5px] leading-snug text-[var(--ink-soft)]">{desc}</div>
    </div>
  );
}

export default function Overview() {
  const t = useT();
  const [s, setS] = useState<Stats | null>(null);

  useEffect(() => {
    const load = () => api.stats().then(setS).catch(() => {});
    load();
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, []);

  if (!s) return <div className="py-24 text-center text-[var(--ink-soft)]">{t("s.loading")}…</div>;
  const reunitedPct = s.total ? Math.round((s.reunited / s.total) * 100) : 0;

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <h1 className="text-[17px] font-extrabold tracking-tight">{t("ov.title")}</h1>
          <p className="text-[12px] text-[var(--ink-soft)]">{t("ov.sub")}</p>
        </div>
        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-[var(--ink-soft)]">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--ok)] animate-livepulse" /> {t("s.live")}
        </span>
      </div>

      {/* Headline counters */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label={t("ov.total")} value={s.total.toLocaleString()} sub={`${s.live_today} ${t("ov.live")}`} />
        <StatCard label={t("ov.reunited")} value={`${reunitedPct}%`} sub={`${s.reunited.toLocaleString()} ${t("ov.families")}`} tone="reunited" />
        <StatCard label={t("ov.avg")} value={s.avg_resolution_hours ? `${s.avg_resolution_hours}h` : "-"} sub={t("ov.avgSub")} />
        <StatCard label={t("m.risk")} value={s.high_risk_unresolved} sub={t("m.riskD")} tone={s.high_risk_unresolved > 0 ? "risk" : undefined} />
      </div>

      {/* Operational metrics */}
      <div className="panel p-4">
        <SectionTitle hint={t("ov.metricsHint")}>{t("ov.metrics")}</SectionTitle>
        <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 lg:grid-cols-6">
          <Metric value={s.cross_center_matches} label={t("m.cross")} desc={t("m.crossD")} />
          <Metric value={s.duplicate_reports_detected} label={t("m.dupe")} desc={t("m.dupeD")} />
          <Metric value={s.cases_missing_name} label={t("m.noName")} desc={t("m.noNameD")} />
          <Metric value={s.cases_missing_mobile} label={t("m.noPhone")} desc={t("m.noPhoneD")} />
          <Metric value={s.requires_escalation} label={t("m.escal")} desc={t("m.escalD")} attention />
          <Metric value={s.high_risk_unresolved} label={t("m.risk")} desc={t("m.riskD")} attention />
        </div>
      </div>

      {/* Reports per day */}
      <div className="panel p-4">
        <SectionTitle hint={t("ov.perDayHint")}>{t("ov.perDay")}</SectionTitle>
        <ResponsiveContainer width="100%" height={190}>
          <AreaChart data={s.timeseries} margin={{ left: -16, right: 6, top: 4 }}>
            <defs>
              <linearGradient id="loadGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={ACCENT} stopOpacity={0.28} />
                <stop offset="100%" stopColor={ACCENT} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: AXIS }} tickFormatter={(d) => d.slice(5)} minTickGap={26} axisLine={{ stroke: GRID }} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: AXIS }} width={32} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tip} />
            <Area type="monotone" dataKey="count" stroke={ACCENT} strokeWidth={2} fill="url(#loadGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <div className="panel p-4">
          <SectionTitle hint={t("ov.byAgeHint")}>{t("ov.byAge")}</SectionTitle>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={pairs(s.by_age_band)} margin={{ left: -22, top: 4 }}>
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: AXIS }} axisLine={{ stroke: GRID }} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: AXIS }} width={28} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tip} cursor={{ fill: "rgba(217,122,31,0.06)" }} />
              <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                {pairs(s.by_age_band).map((d) => (
                  <Cell key={d.name} fill={["61-70", "71-80", "80+", "0-12"].includes(d.name) ? DANGER : GRAY} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="panel p-4">
          <SectionTitle hint={`${reunitedPct}% ${t("ov.reunited").toLowerCase()}`}>{t("ov.outcomes")}</SectionTitle>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={pairs(s.by_status)} dataKey="value" nameKey="name" innerRadius={46} outerRadius={72} paddingAngle={2} stroke="none">
                {pairs(s.by_status).map((d) => <Cell key={d.name} fill={toneColor(d.name)} />)}
              </Pie>
              <Tooltip contentStyle={tip} />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-1 flex flex-wrap justify-center gap-x-3 gap-y-1 text-[11px] text-[var(--ink-soft)]">
            {pairs(s.by_status).map((d) => (
              <span key={d.name} className="inline-flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: toneColor(d.name) }} />{d.name}
              </span>
            ))}
          </div>
        </div>

        <div className="panel p-4">
          <SectionTitle hint={t("ov.languagesHint")}>{t("ov.languages")}</SectionTitle>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart layout="vertical" data={pairs(s.by_language).slice(0, 8)} margin={{ left: 16, right: 12 }}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#5c656f" }} width={66} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tip} cursor={{ fill: "rgba(217,122,31,0.06)" }} />
              <Bar dataKey="value" radius={[0, 3, 3, 0]} fill={ACCENT} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="panel p-4">
          <SectionTitle>{t("ov.channels")}</SectionTitle>
          <div className="space-y-2.5">
            {pairs(s.by_channel).map((d) => {
              const max = Math.max(...Object.values(s.by_channel));
              return (
                <div key={d.name}>
                  <div className="flex justify-between text-[12px]"><span className="capitalize">{d.name}</span><span className="mono font-semibold text-[var(--ink-soft)]">{d.value}</span></div>
                  <div className="mt-1 h-1.5 rounded-full bg-[var(--surface-2)]">
                    <div className="h-1.5 rounded-full" style={{ width: `${(d.value / max) * 100}%`, background: ACCENT }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="panel p-4">
          <SectionTitle hint={t("ov.hotspotsHint")}>{t("ov.hotspots")}</SectionTitle>
          <ol className="space-y-1.5 text-[13px]">
            {Object.entries(s.top_locations).slice(0, 6).map(([name, n], i) => (
              <li key={name} className="flex items-center gap-2.5">
                <span className="mono grid h-5 w-5 place-items-center rounded border border-[var(--line)] text-[10px] font-bold text-[var(--ink-soft)]">{i + 1}</span>
                <span className="flex-1 truncate">{name}</span>
                <span className="mono text-[12px] font-semibold text-[var(--ink-soft)]">{n}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}
