import { useEffect, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { api, type Stats } from "../lib/api";
import { Eyebrow, SectionTitle, StatCard } from "../components/ui";
import { useT } from "../lib/i18n";

// Duotone palette: saffron is the only hue; everything else is warm gray / ink.
const SAFFRON = "#e0852b";
const SAFFRON_SOFT = "#f0b878";
const INK = "#1f1a14";
const GRAY = "#b6ab98";
const GRAY_SOFT = "#ddd4c5";
const GRID = "#ece6db";
const AXIS = "#9a8f7e";
const tip = { borderRadius: 12, border: "1px solid #ece6db", fontSize: 12, boxShadow: "0 10px 30px -20px rgba(31,26,20,.4)" };

// Outcome rendered by saffron-vs-gray, not by a rainbow of status hues.
const STATUS_COLOR: Record<string, string> = {
  Reunited: SAFFRON, Pending: GRAY, "Transferred to hospital": GRAY_SOFT,
  Unresolved: INK, Closed: GRAY_SOFT, Duplicate: GRAY_SOFT, active: GRAY,
};

function pairs(rec: Record<string, number>) {
  return Object.entries(rec).map(([name, value]) => ({ name, value }));
}

function Metric({ value, label, desc, attention }: { value: number; label: string; desc: string; attention?: boolean }) {
  return (
    <div
      className="rounded-2xl border bg-white p-4"
      style={{
        borderColor: attention && value > 0 ? "rgba(224,133,43,.4)" : "var(--color-line)",
        background: attention && value > 0 ? "rgba(224,133,43,.05)" : "#fff",
      }}
    >
      <div className="serif text-[30px] leading-none tracking-tight" style={{ color: attention && value > 0 ? SAFFRON : INK }}>
        {value}
      </div>
      <div className="mt-1.5 text-[13px] font-semibold">{label}</div>
      <div className="mt-0.5 text-[12px] leading-snug text-[var(--color-ink-soft)]">{desc}</div>
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

  if (!s) return <div className="py-24 text-center text-[var(--color-ink-soft)]">{t("s.loading")}…</div>;
  const reunitedPct = s.total ? Math.round((s.reunited / s.total) * 100) : 0;

  return (
    <div className="space-y-9">
      {/* Hero */}
      <section className="pt-2 text-center">
        <div className="flex justify-center"><Eyebrow center>{t("app.place")}</Eyebrow></div>
        <h1 className="serif mx-auto mt-4 max-w-3xl text-[36px] font-semibold leading-[1.12] tracking-tight md:text-[46px]">
          {t("ov.title")}
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-[16px] leading-relaxed text-[var(--color-ink-soft)]">{t("ov.sub")}</p>
      </section>

      {/* Headline counters */}
      <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label={t("ov.total")} value={s.total.toLocaleString()}
          sub={<span className="font-semibold text-[var(--color-saffron)]">{s.live_today} {t("ov.live")}</span>} />
        <StatCard label={t("ov.reunited")} value={`${reunitedPct}%`} sub={`${s.reunited.toLocaleString()} ${t("ov.families")}`} />
        <StatCard label={t("ov.avg")} value={s.avg_resolution_hours ? `${s.avg_resolution_hours}h` : "-"} sub={t("ov.avgSub")} />
        <StatCard label={t("ov.dupes")} value={s.duplicate_reports_detected} sub={t("ov.dupesSub")} />
      </section>

      {/* Judge-aligned operational metrics */}
      <section className="card p-6">
        <SectionTitle hint={t("ov.metricsHint")}>{t("ov.metrics")}</SectionTitle>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          <Metric value={s.cross_center_matches} label={t("m.cross")} desc={t("m.crossD")} />
          <Metric value={s.duplicate_reports_detected} label={t("m.dupe")} desc={t("m.dupeD")} />
          <Metric value={s.cases_missing_name} label={t("m.noName")} desc={t("m.noNameD")} />
          <Metric value={s.cases_missing_mobile} label={t("m.noPhone")} desc={t("m.noPhoneD")} />
          <Metric value={s.requires_escalation} label={t("m.escal")} desc={t("m.escalD")} attention />
          <Metric value={s.high_risk_unresolved} label={t("m.risk")} desc={t("m.riskD")} attention />
        </div>
      </section>

      {/* Reports per day */}
      <section className="card p-6">
        <SectionTitle hint={t("ov.perDayHint")}>{t("ov.perDay")}</SectionTitle>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={s.timeseries} margin={{ left: -14, right: 8, top: 6 }}>
            <defs>
              <linearGradient id="loadGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={SAFFRON} stopOpacity={0.3} />
                <stop offset="100%" stopColor={SAFFRON} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: AXIS }} tickFormatter={(d) => d.slice(5)} minTickGap={26} axisLine={{ stroke: GRID }} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: AXIS }} width={34} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={tip} />
            <Area type="monotone" dataKey="count" stroke={SAFFRON} strokeWidth={2} fill="url(#loadGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="card p-6">
          <SectionTitle hint={t("ov.byAgeHint")}>{t("ov.byAge")}</SectionTitle>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={pairs(s.by_age_band)} margin={{ left: -22, top: 4 }}>
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: AXIS }} axisLine={{ stroke: GRID }} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: AXIS }} width={30} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tip} cursor={{ fill: "rgba(224,133,43,0.06)" }} />
              <Bar dataKey="value" radius={[5, 5, 0, 0]}>
                {pairs(s.by_age_band).map((d) => (
                  <Cell key={d.name} fill={d.name === "61-70" ? SAFFRON : GRAY_SOFT} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-6">
          <SectionTitle hint={`${reunitedPct}% ${t("ov.reunited").toLowerCase()}`}>{t("ov.outcomes")}</SectionTitle>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={pairs(s.by_status)} dataKey="value" nameKey="name" innerRadius={50} outerRadius={78} paddingAngle={2} stroke="none">
                {pairs(s.by_status).map((d) => <Cell key={d.name} fill={STATUS_COLOR[d.name] ?? GRAY_SOFT} />)}
              </Pie>
              <Tooltip contentStyle={tip} />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1 text-[11px] text-[var(--color-ink-soft)]">
            {pairs(s.by_status).map((d) => (
              <span key={d.name} className="inline-flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: STATUS_COLOR[d.name] ?? GRAY_SOFT }} />{d.name}
              </span>
            ))}
          </div>
        </div>

        <div className="card p-6">
          <SectionTitle hint={t("ov.languagesHint")}>{t("ov.languages")}</SectionTitle>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart layout="vertical" data={pairs(s.by_language).slice(0, 8)} margin={{ left: 16, right: 12 }}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#6c6358" }} width={66} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tip} cursor={{ fill: "rgba(224,133,43,0.06)" }} />
              <Bar dataKey="value" radius={[0, 5, 5, 0]}>
                {pairs(s.by_language).slice(0, 8).map((_, i) => (
                  <Cell key={i} fill={i === 0 ? SAFFRON : SAFFRON_SOFT} fillOpacity={i === 0 ? 1 : 0.85 - i * 0.08} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="card p-6">
          <SectionTitle>{t("ov.channels")}</SectionTitle>
          <div className="space-y-3">
            {pairs(s.by_channel).map((d) => {
              const max = Math.max(...Object.values(s.by_channel));
              const isLive = d.name !== "seed";
              return (
                <div key={d.name}>
                  <div className="flex justify-between text-xs"><span className="capitalize">{d.name}</span><span className="font-semibold text-[var(--color-ink-soft)]">{d.value}</span></div>
                  <div className="mt-1.5 h-1.5 rounded-full bg-[var(--color-bg-soft)]">
                    <div className="h-1.5 rounded-full" style={{ width: `${(d.value / max) * 100}%`, background: isLive ? SAFFRON : GRAY_SOFT }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card p-6">
          <SectionTitle hint={t("ov.hotspotsHint")}>{t("ov.hotspots")}</SectionTitle>
          <ol className="space-y-2 text-sm">
            {Object.entries(s.top_locations).slice(0, 6).map(([name, n], i) => (
              <li key={name} className="flex items-center gap-2.5">
                <span className="grid h-6 w-6 place-items-center rounded-full border border-[var(--color-line)] text-[11px] font-bold text-[var(--color-ink-soft)]">{i + 1}</span>
                <span className="flex-1 truncate">{name}</span>
                <span className="text-xs font-semibold text-[var(--color-ink-soft)]">{n}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>
    </div>
  );
}
