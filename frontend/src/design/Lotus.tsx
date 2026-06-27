/** NANDI mark — a simple lotus, drawn as a solid silhouette. Five hand-tuned
 *  petals fanning from a single base: pointed tips, full bellies. No gradient,
 *  no stroke — one ink-coloured shape. Inherits `currentColor`. */
export function Lotus({ size = 34, className = "" }: { size?: number; className?: string }) {
  // one long petal (centre + inner pair) and one short petal (outer pair),
  // both pointing straight up from the pivot; placed by rotation around the base.
  const long = "M0 0 C -9 -16 -5 -44 0 -60 C 5 -44 9 -16 0 0 Z";
  const short = "M0 0 C -8 -12 -4 -33 0 -47 C 4 -33 8 -12 0 0 Z";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 104"
      className={`text-[var(--color-ink)] ${className}`}
      aria-hidden="true"
    >
      <g transform="translate(60 84)" fill="currentColor">
        <path d={short} transform="rotate(-64)" />
        <path d={short} transform="rotate(64)" />
        <path d={long} transform="rotate(-32)" />
        <path d={long} transform="rotate(32)" />
        <path d={long} />
      </g>
    </svg>
  );
}

/** Quiet line lotus for hero / background washes. Same five-petal geometry,
 *  drawn as a hairline outline. Uses `currentColor`. */
export function Mandala({ className = "" }: { className?: string }) {
  const long = "M0 0 C -34 -60 -20 -166 0 -226 C 20 -166 34 -60 0 0 Z";
  const short = "M0 0 C -30 -46 -16 -124 0 -178 C 16 -124 30 -46 0 0 Z";
  return (
    <svg viewBox="0 0 400 400" className={className} aria-hidden="true">
      <g transform="translate(200 312)" fill="none" stroke="currentColor" strokeWidth="1">
        <path d={short} transform="rotate(-66)" />
        <path d={short} transform="rotate(66)" />
        <path d={long} transform="rotate(-34)" />
        <path d={long} transform="rotate(34)" />
        <path d={long} />
      </g>
    </svg>
  );
}
