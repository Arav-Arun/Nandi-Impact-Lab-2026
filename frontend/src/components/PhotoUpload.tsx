import { useRef, useState } from "react";
import { api } from "../lib/api";
import { useT } from "../lib/i18n";

/**
 * PhotoUpload — optional person-photo entry point.
 *
 * Uploads the chosen image to POST /api/v1/media/upload immediately and reports
 * the resulting `photo_url` upward via onChange. The parent stores that url and
 * passes it to the intake routes, where the backend computes the face embedding
 * (joining the photo to the matching pipeline). Photos are optional everywhere —
 * this never blocks a submission.
 */
export function PhotoUpload({
  photoUrl,
  onChange,
  compact = false,
}: {
  photoUrl: string | null;
  onChange: (url: string | null) => void;
  compact?: boolean;
}) {
  const t = useT();
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-picking the same file
    if (!file) return;
    setError(null);
    setPreview(URL.createObjectURL(file));
    setBusy(true);
    try {
      const res = await api.uploadPhoto(file);
      onChange(res.photo_url);
    } catch (err) {
      setError((err as Error).message);
      setPreview(null);
      onChange(null);
    } finally {
      setBusy(false);
    }
  }

  function remove() {
    setPreview(null);
    setError(null);
    onChange(null);
  }

  const shown = preview ?? photoUrl;
  const size = compact ? "h-16 w-16" : "h-20 w-20";

  return (
    <div className="flex items-center gap-3">
      <input ref={inputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={onPick} />
      {shown ? (
        <div className="relative">
          <img src={shown} alt="" className={`${size} rounded-xl object-cover ring-1 ring-[var(--color-line)]`} />
          {busy && (
            <div className="absolute inset-0 grid place-items-center rounded-xl bg-white/60 text-[10px] font-semibold animate-livepulse">
              {t("in.uploading")}…
            </div>
          )}
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className={`${size} grid shrink-0 place-items-center rounded-xl border-2 border-dashed border-[var(--color-line)] bg-white text-2xl text-[var(--color-ink-soft)] transition hover:border-[var(--color-saffron)]/50`}
          aria-label={t("in.addPhoto")}
        >
          📷
        </button>
      )}
      <div className="min-w-0">
        {shown ? (
          <button type="button" onClick={remove} className="text-xs font-semibold text-[var(--color-danger)]">
            ✕ {t("in.removePhoto")}
          </button>
        ) : (
          <button type="button" onClick={() => inputRef.current?.click()} className="text-sm font-semibold text-[var(--color-ink)]">
            {t("in.addPhoto")}
          </button>
        )}
        {!compact && <div className="mt-0.5 text-xs text-[var(--color-ink-soft)]">{t("in.photoHint")}</div>}
        {error && <div className="mt-0.5 text-xs text-[var(--color-danger)]">{error}</div>}
      </div>
    </div>
  );
}
