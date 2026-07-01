/** Clean line icons (1.6 stroke, currentColor) - no emoji. */
import type { SVGProps } from "react";

const base = (p: SVGProps<SVGSVGElement>) => ({
  width: 18, height: 18, viewBox: "0 0 24 24", fill: "none",
  stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const, ...p,
});

export const IconMic = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
);
export const IconStop = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><rect x="6" y="6" width="12" height="12" rx="2.5" /></svg>
);
export const IconWeb = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c2.5 2.5 2.5 15 0 18M12 3c-2.5 2.5-2.5 15 0 18" /></svg>
);
export const IconTelegram = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M21 4 3 11l5 2 2 6 3-4 5 4 3-15Z" /><path d="M8 13l8-5" /></svg>
);
export const IconWhatsApp = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M4 20l1.5-4A8 8 0 1 1 9 19.5L4 20Z" /><path d="M9 9c0 4 2 6 6 6 .8 0 1.2-1 .7-1.6l-1.3-1c-.4-.3-.8 0-1 .3-1.2-.3-1.9-1-2.2-2.2.3-.2.6-.6.3-1l-1-1.3C9.6 6.8 8.6 7.2 9 9Z" /></svg>
);
export const IconPhone = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M5 4h3l1.5 4-2 1.5a11 11 0 0 0 5 5l1.5-2 4 1.5V18a2 2 0 0 1-2 2A14 14 0 0 1 4 6a2 2 0 0 1 1-2Z" /></svg>
);
export const IconArchive = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><rect x="3" y="4" width="18" height="4" rx="1" /><path d="M5 8v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8M10 12h4" /></svg>
);
export const IconCheck = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M5 13l4 4L19 7" /></svg>
);
export const IconArrow = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M5 12h14M13 6l6 6-6 6" /></svg>
);
export const IconSound = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M4 9v6h4l5 4V5L8 9H4ZM17 9a4 4 0 0 1 0 6M19.5 7a7 7 0 0 1 0 10" /></svg>
);

/** Sarvam's small four-point sparkle, used as a bullet marker. */
export const Sparkle = ({ className = "" }: { className?: string }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" className={className} aria-hidden="true">
    <path d="M12 2c.6 5 1.8 7.4 8 8-6.2.6-7.4 3-8 8-.6-5-1.8-7.4-8-8 6.2-.6 7.4-3 8-8Z" fill="currentColor" />
  </svg>
);
