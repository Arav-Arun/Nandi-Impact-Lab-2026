import { useEffect, useMemo, useState } from "react";
import { api, type BlastResult, type Channels, type SubscribersResult, type Zone } from "../lib/api";
import { Eyebrow, SectionTitle } from "../components/ui";
import { useT } from "../lib/i18n";

const inputCls =
  "w-full rounded-xl border border-[var(--color-line)] bg-white px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-[var(--color-saffron)]/30";

const LABEL: Record<string, string> = { telegram: "Telegram", whatsapp: "WhatsApp", sms: "SMS", email: "Email" };
const MONO: Record<string, string> = { telegram: "T", whatsapp: "W", sms: "S", email: "E" };

function ChannelChip({ name, live }: { name: string; live: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold"
      style={{
        borderColor: live ? "rgba(224,133,43,.4)" : "var(--color-line)",
        background: live ? "rgba(224,133,43,.08)" : "var(--color-bg-soft)",
        color: live ? "var(--color-saffron-deep)" : "var(--color-ink-soft)",
      }}
      title={live ? "Key configured, messages send for real" : "No key, logs a no-op but still targets recipients"}
    >
      {LABEL[name] ?? name}
      <span className={`h-1.5 w-1.5 rounded-full`} style={{ background: live ? "var(--color-saffron)" : "var(--color-line-2)" }} />
    </span>
  );
}

function Mono({ ch }: { ch: string }) {
  return (
    <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-[var(--color-bg-soft)] text-[10px] font-bold text-[var(--color-ink-soft)]">
      {MONO[ch] ?? "•"}
    </span>
  );
}

export default function Blast() {
  const t = useT();
  const [channels, setChannels] = useState<Channels | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [subs, setSubs] = useState<SubscribersResult | null>(null);

  const [zoneId, setZoneId] = useState<string>("");
  const [subject, setSubject] = useState("NANDI alert");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<BlastResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [sub, setSub] = useState({ channel: "telegram", address: "", zone_id: "", name: "" });
  const [subBusy, setSubBusy] = useState(false);

  const refresh = () => {
    api.zones().then(setZones).catch(() => {});
    api.subscribers().then(setSubs).catch(() => {});
  };

  useEffect(() => {
    api.channels().then(setChannels).catch(() => {});
    refresh();
  }, []);

  useEffect(() => {
    if (!zoneId && zones.length) setZoneId(zones[0].id);
  }, [zones, zoneId]);

  const selectedZone = useMemo(() => zones.find((z) => z.id === zoneId) ?? null, [zones, zoneId]);
  const anyLive = channels ? Object.values(channels).some(Boolean) : false;

  async function sendBlast() {
    if (!zoneId || !message.trim()) return;
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      const r = await api.blastZone(zoneId, message.trim(), subject.trim() || "NANDI alert");
      setResult(r);
      setMessage("");
      refresh();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function addSubscriber() {
    if (!sub.address.trim()) return;
    setSubBusy(true);
    try {
      await api.addSubscriber({
        channel: sub.channel,
        address: sub.address.trim(),
        zone_id: sub.zone_id || null,
        name: sub.name || null,
      });
      setSub({ ...sub, address: "", name: "" });
      refresh();
    } catch (e) {
      alert("Could not add subscriber: " + (e as Error).message);
    } finally {
      setSubBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="text-center">
        <div className="flex justify-center"><Eyebrow center>{t("bl.eyebrow")}</Eyebrow></div>
        <h1 className="serif mx-auto mt-4 max-w-2xl text-[32px] font-semibold leading-[1.14] tracking-tight md:text-[40px]">
          {t("bl.title")}
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-[16px] leading-relaxed text-[var(--color-ink-soft)]">{t("bl.sub")}</p>
      </section>

      {/* Channel availability */}
      <section className="card p-5">
        <SectionTitle hint={anyLive ? t("bl.ready") : t("bl.noKeys")}>{t("bl.channels")}</SectionTitle>
        <div className="flex flex-wrap gap-2">
          {channels
            ? Object.entries(channels).map(([name, live]) => <ChannelChip key={name} name={name} live={live} />)
            : <span className="text-sm text-[var(--color-ink-soft)]">{t("s.loading")}…</span>}
        </div>
        {!anyLive && (
          <p className="mt-3 rounded-xl border border-[var(--color-line)] bg-[var(--color-bg-soft)] p-3 text-xs text-[var(--color-ink-soft)]">
            {t("bl.noKeyNote")}
          </p>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        {/* Compose blast */}
        <section className="card p-5">
          <SectionTitle hint={selectedZone ? `${selectedZone.reachable} ${t("bl.reachable")}` : undefined}>
            {t("bl.blastZone")}
          </SectionTitle>

          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-[var(--color-ink-soft)]">{t("bl.targetZone")}</label>
              <select className={inputCls + " mt-1"} value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
                {zones.map((z) => (
                  <option key={z.id} value={z.id}>
                    {z.name} · {z.venue} · {z.reachable} {t("bl.reachableShort")}
                  </option>
                ))}
              </select>
              <p className="mt-1.5 text-[11px] text-[var(--color-ink-soft)]">{t("bl.adjacentNote")}</p>
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--color-ink-soft)]">{t("bl.subject")}</label>
              <input className={inputCls + " mt-1"} value={subject} onChange={(e) => setSubject(e.target.value)} />
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--color-ink-soft)]">{t("bl.message")}</label>
              <textarea
                className={inputCls + " mt-1"}
                rows={4}
                placeholder={t("bl.messagePlaceholder")}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </div>

            <button
              onClick={sendBlast}
              disabled={busy || !zoneId || !message.trim()}
              className="nandi-gradient w-full rounded-xl py-3 font-bold text-white disabled:opacity-60"
            >
              {busy ? `${t("bl.sending")}…` : `${t("bl.send")} · ${selectedZone?.name ?? ""}`}
            </button>

            {err && <div className="rounded-xl border border-[var(--color-danger)]/30 bg-[rgba(180,100,26,0.06)] p-3 text-sm text-[var(--color-danger)]">{err}</div>}

            {result && (
              <div className="rounded-xl border border-[var(--color-saffron)]/30 bg-[rgba(224,133,43,0.07)] p-4">
                <div className="font-bold text-[var(--color-saffron-deep)]">✓ {t("bl.dispatched")}</div>
                <p className="mt-1 text-sm">{t("bl.targeted", { n: result.targeted, z: result.zones.length })}</p>
                {Object.keys(result.channels).length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {Object.entries(result.channels).map(([ch, v]) => (
                      <span key={ch} className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium" style={{ border: "1px solid var(--color-line)" }}>
                        {(LABEL[ch] ?? ch)}: {v.sent}/{v.targeted} {t("bl.sentOf")}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="mt-1 text-xs text-[var(--color-ink-soft)]">{t("bl.noRecipients")}</p>
                )}
              </div>
            )}
          </div>
        </section>

        {/* Subscribers */}
        <section className="card p-5">
          <SectionTitle hint={subs ? `${subs.total} ${t("bl.total")}` : undefined}>{t("bl.subscribers")}</SectionTitle>

          <div className="grid grid-cols-2 gap-2">
            <select className={inputCls} value={sub.channel} onChange={(e) => setSub({ ...sub, channel: e.target.value })}>
              <option value="telegram">Telegram</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="sms">SMS</option>
              <option value="email">Email</option>
            </select>
            <select className={inputCls} value={sub.zone_id} onChange={(e) => setSub({ ...sub, zone_id: e.target.value })}>
              <option value="">{t("bl.noZone")}</option>
              {zones.map((z) => (
                <option key={z.id} value={z.id}>{z.name}</option>
              ))}
            </select>
            <input
              className={inputCls + " col-span-2"}
              placeholder={
                sub.channel === "email" ? t("bl.addrEmail") :
                sub.channel === "telegram" ? t("bl.addrTelegram") : t("bl.addrPhone")
              }
              value={sub.address}
              onChange={(e) => setSub({ ...sub, address: e.target.value })}
            />
            <input className={inputCls + " col-span-2"} placeholder={t("bl.nameOpt")} value={sub.name} onChange={(e) => setSub({ ...sub, name: e.target.value })} />
            <button
              onClick={addSubscriber}
              disabled={subBusy || !sub.address.trim()}
              className="btn-dark col-span-2 py-2.5 text-sm disabled:opacity-60"
            >
              {subBusy ? `${t("bl.adding")}…` : `+ ${t("bl.addSub")}`}
            </button>
          </div>

          {subs && subs.total > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {Object.entries(subs.by_channel).map(([ch, n]) => (
                <span key={ch} className="rounded-full bg-[var(--color-bg-soft)] px-2.5 py-1 text-[11px] font-semibold text-[var(--color-ink-soft)]">
                  {(LABEL[ch] ?? ch)} · {n}
                </span>
              ))}
            </div>
          )}

          <div className="mt-3 max-h-72 space-y-1.5 overflow-y-auto">
            {subs?.subscribers.map((s, i) => {
              const z = zones.find((zz) => zz.id === s.zone_id);
              return (
                <div key={i} className="flex items-center gap-2 rounded-lg border border-[var(--color-line)] px-3 py-2 text-xs">
                  <Mono ch={s.channel} />
                  <span className="truncate font-medium">{s.name || s.address}</span>
                  <span className="ml-auto shrink-0 text-[var(--color-ink-soft)]">{z?.name ?? "-"}</span>
                </div>
              );
            })}
            {subs && subs.total === 0 && (
              <p className="text-sm text-[var(--color-ink-soft)]">{t("bl.noSubs")}</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
