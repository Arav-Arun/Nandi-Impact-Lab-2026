import type { ReactNode } from "react";
import { IconArchive, IconPhone, IconTelegram, IconWeb, IconWhatsApp } from "../design/Icons";

// Duotone: channels are distinguished by icon + label, not by hue. Saffron marks
// the live "web" channel; everything else is warm gray.
const CHANNELS: Record<string, { label: string; Icon: typeof IconWeb; color: string }> = {
  web: { label: "Web", Icon: IconWeb, color: "var(--color-saffron)" },
  telegram: { label: "Telegram", Icon: IconTelegram, color: "var(--color-ink-soft)" },
  whatsapp: { label: "WhatsApp", Icon: IconWhatsApp, color: "var(--color-ink-soft)" },
  ivr: { label: "Call", Icon: IconPhone, color: "var(--color-ink-soft)" },
  booth: { label: "Booth", Icon: IconArchive, color: "var(--color-saffron-deep)" },
  seed: { label: "Archive", Icon: IconArchive, color: "var(--color-ink-soft)" },
};

export function ChannelBadge({ channel }: { channel: string }) {
  const c = CHANNELS[channel] ?? CHANNELS.seed;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-line)] bg-white px-2.5 py-1 text-[11px] font-semibold" style={{ color: c.color }}>
      <c.Icon width={13} height={13} />
      {c.label}
    </span>
  );
}

const STATUS_DOT: Record<string, string> = {
  active: "var(--color-warn)",
  unmatched: "var(--color-warn)",
  Pending: "var(--color-warn)",
  matched: "var(--color-green)",
  Reunited: "var(--color-green)",
  "Transferred to hospital": "var(--color-indigo)",
  closed: "#9a9aa8",
  Unresolved: "var(--color-danger)",
};

export function StatusPill({ status }: { status: string }) {
  const dot = STATUS_DOT[status] ?? "#9a9aa8";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-line)] bg-white px-2.5 py-1 text-[11px] font-semibold text-[var(--color-ink-soft)]">
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: dot }} />
      {status}
    </span>
  );
}

export function StatCard({
  label, value, sub,
}: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="card p-5">
      <div className="text-[12px] font-medium text-[var(--color-ink-soft)]">{label}</div>
      <div className="serif mt-1.5 text-[34px] leading-none tracking-tight">{value}</div>
      {sub && <div className="mt-2 text-xs text-[var(--color-ink-soft)]">{sub}</div>}
    </div>
  );
}

export function SectionTitle({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <div className="mb-4 flex items-baseline justify-between gap-3">
      <h3 className="text-[13px] font-bold tracking-tight text-[var(--color-ink)]">{children}</h3>
      {hint && <span className="text-[11px] text-[var(--color-ink-soft)]">{hint}</span>}
    </div>
  );
}

/** Sarvam-style eyebrow: small caps text flanked by thin rules. */
export function Eyebrow({ children, center = false }: { children: ReactNode; center?: boolean }) {
  return (
    <div className={`flex items-center gap-3 ${center ? "justify-center" : ""}`}>
      <span className="h-px w-8 bg-[var(--color-line-2)]" />
      <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-indigo)]">{children}</span>
      <span className="h-px w-8 bg-[var(--color-line-2)]" />
    </div>
  );
}
