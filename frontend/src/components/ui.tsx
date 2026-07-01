import type { ReactNode } from "react";
import { IconArchive, IconPhone, IconTelegram, IconWeb, IconWhatsApp } from "./Icons";

// ── Channels ────────────────────────────────────────────────────────────────
const CHANNELS: Record<string, { label: string; Icon: typeof IconWeb }> = {
  web: { label: "Web", Icon: IconWeb },
  telegram: { label: "Telegram", Icon: IconTelegram },
  whatsapp: { label: "WhatsApp", Icon: IconWhatsApp },
  ivr: { label: "Call", Icon: IconPhone },
  booth: { label: "Booth", Icon: IconArchive },
  seed: { label: "Archive", Icon: IconArchive },
};

export function ChannelBadge({ channel }: { channel: string }) {
  const c = CHANNELS[channel] ?? CHANNELS.seed;
  return (
    <span className="inline-flex items-center gap-1 rounded border border-[var(--line)] bg-[var(--surface-2)] px-1.5 py-0.5 text-[10.5px] font-semibold text-[var(--ink-soft)]">
      <c.Icon width={11} height={11} />
      {c.label}
    </span>
  );
}

// ── Status ────────────────────────────────────────────────────────────────
type Tone = "active" | "matched" | "reunited" | "risk" | "closed";

const TONES: Record<Tone, { fg: string; bg: string }> = {
  active: { fg: "var(--warn)", bg: "var(--warn-soft)" },
  matched: { fg: "var(--info)", bg: "var(--info-soft)" },
  reunited: { fg: "var(--ok)", bg: "var(--ok-soft)" },
  risk: { fg: "var(--danger)", bg: "var(--danger-soft)" },
  closed: { fg: "var(--ink-soft)", bg: "var(--surface-2)" },
};

export function statusTone(status: string): Tone {
  const s = status.toLowerCase();
  if (["reunited", "resolved"].some((x) => s.includes(x))) return "reunited";
  if (["matched", "pickup"].some((x) => s.includes(x))) return "matched";
  if (["unresolved", "escalat", "risk", "overdue"].some((x) => s.includes(x))) return "risk";
  if (["closed", "transfer", "hospital"].some((x) => s.includes(x))) return "closed";
  return "active";
}

export function StatusPill({ status }: { status: string }) {
  const tone = TONES[statusTone(status)];
  return (
    <span className="pill" style={{ color: tone.fg, background: tone.bg }}>
      <span className="pill-dot" />
      {status}
    </span>
  );
}

// ── Layout primitives ───────────────────────────────────────────────────────
export function StatCard({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: Tone }) {
  const accent = tone ? TONES[tone].fg : "var(--ink)";
  return (
    <div className="panel px-3.5 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--ink-faint)]">{label}</div>
      <div className="mono mt-1 text-[26px] font-bold leading-none" style={{ color: accent }}>{value}</div>
      {sub && <div className="mt-1.5 text-[11.5px] text-[var(--ink-soft)]">{sub}</div>}
    </div>
  );
}

export function SectionTitle({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h3 className="text-[12px] font-bold uppercase tracking-wide text-[var(--ink)]">{children}</h3>
      {hint && <span className="text-[11px] text-[var(--ink-soft)]">{hint}</span>}
    </div>
  );
}

export function Eyebrow({ children, center = false }: { children: ReactNode; center?: boolean }) {
  return (
    <div className={`flex items-center gap-2 ${center ? "justify-center" : ""}`}>
      <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--accent-ink)]">{children}</span>
    </div>
  );
}
