import { useEffect, useMemo, useState } from "react";
import { api, type BlastResult, type Channels, type SubscribersResult, type Zone } from "../lib/api";
import { SectionTitle } from "../components/ui";
import { useT } from "../lib/i18n";

function ChannelChip({ name, live }: { name: string; live: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded border px-2 py-1 text-[11px] font-bold uppercase tracking-wide"
      style={{
        borderColor: live ? "var(--ok)" : "var(--line)",
        background: live ? "var(--ok-soft)" : "var(--surface-2)",
        color: live ? "var(--ok)" : "var(--ink-soft)",
      }}
      title={live ? "Key configured - sends dispatch for real" : "No key - sends are logged no-ops"}
    >
      {name}
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: live ? "var(--ok)" : "var(--line-2)" }} />
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

  const [channelInput, setChannelInput] = useState("");
  const [email, setEmail] = useState({ address: "", zone_id: "", name: "" });
  const [emailBusy, setEmailBusy] = useState(false);

  const refresh = () => {
    api.zones().then(setZones).catch(() => {});
    api.subscribers().then(setSubs).catch(() => {});
  };
  useEffect(() => { api.channels().then(setChannels).catch(() => {}); refresh(); }, []);
  useEffect(() => { if (!zoneId && zones.length) setZoneId(zones[0].id); }, [zones, zoneId]);

  const selectedZone = useMemo(() => zones.find((z) => z.id === zoneId) ?? null, [zones, zoneId]);
  useEffect(() => { setChannelInput(selectedZone?.telegram_channel ?? ""); }, [selectedZone]);
  const anyLive = channels ? Object.values(channels).some(Boolean) : false;

  async function sendBlast() {
    if (!zoneId || !message.trim()) return;
    setBusy(true); setErr(null); setResult(null);
    try {
      setResult(await api.blastZone(zoneId, message.trim(), subject.trim() || "NANDI alert"));
      setMessage(""); refresh();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  async function saveChannel() {
    if (!zoneId) return;
    try {
      await api.setZoneChannel(zoneId, channelInput.trim() || null);
      refresh();
    } catch (e) { alert("Could not set channel: " + (e as Error).message); }
  }

  async function addEmail() {
    if (!email.address.trim()) return;
    setEmailBusy(true);
    try {
      await api.addSubscriber({ channel: "email", address: email.address.trim(), zone_id: email.zone_id || null, name: email.name || null });
      setEmail({ address: "", zone_id: "", name: "" });
      refresh();
    } catch (e) { alert("Could not add: " + (e as Error).message); } finally { setEmailBusy(false); }
  }

  const emailSubs = subs?.subscribers.filter((s) => s.channel === "email") ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-[17px] font-extrabold tracking-tight">{t("bl.title")}</h1>
          <p className="max-w-2xl text-[12px] text-[var(--ink-soft)]">{t("bl.sub")}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold text-[var(--ink-soft)]">{t("bl.channels")}: {anyLive ? t("bl.ready") : t("bl.noKeys")}</span>
          {channels
            ? Object.entries(channels).map(([name, live]) => <ChannelChip key={name} name={name} live={live} />)
            : <span className="text-[12px] text-[var(--ink-soft)]">{t("s.loading")}…</span>}
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-[1.3fr_1fr]">
        {/* Compose */}
        <section className="panel p-4">
          <SectionTitle hint={selectedZone?.telegram_channel ? selectedZone.telegram_channel : t("bl.noChannelSet")}>{t("bl.blastZone")}</SectionTitle>
          <div className="space-y-3">
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-[var(--ink-faint)]">{t("bl.targetZone")}</label>
              <select className="field mt-1" value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
                {zones.map((z) => <option key={z.id} value={z.id}>{z.name} · {z.venue}</option>)}
              </select>
              <p className="mt-1 text-[11px] text-[var(--ink-soft)]">{t("bl.adjacentNote")}</p>
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-[var(--ink-faint)]">{t("bl.subject")}</label>
              <input className="field mt-1" value={subject} onChange={(e) => setSubject(e.target.value)} />
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-[var(--ink-faint)]">{t("bl.message")}</label>
              <textarea className="field mt-1" rows={4} placeholder={t("bl.messagePlaceholder")} value={message} onChange={(e) => setMessage(e.target.value)} />
            </div>
            <button onClick={sendBlast} disabled={busy || !zoneId || !message.trim()} className="btn btn-primary w-full py-2.5">
              {busy ? `${t("bl.sending")}…` : `${t("bl.send")} · ${selectedZone?.name ?? ""}`}
            </button>

            {err && <div className="rounded-md border border-[var(--danger)] bg-[var(--danger-soft)] p-2.5 text-[13px] text-[var(--danger)]">{err}</div>}

            {result && (
              <div className="rounded-md border border-[var(--ok)] bg-[var(--ok-soft)] p-3">
                <div className="text-[13px] font-bold text-[var(--ok)]">✓ {t("bl.dispatched")}</div>
                <p className="mono mt-1 text-[13px]">{t("bl.reach")}: <b>{result.targeted.toLocaleString()}</b></p>
                <p className="mt-1 text-[12px] text-[var(--ink-soft)]">{t("bl.postedTo", { n: result.channels_posted.length })} · {t("bl.emailRecipients")}: {result.email.sent}/{result.email.targeted}</p>
                {result.channels_posted.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {result.channels_posted.map((c) => (
                      <span key={c.channel} className="mono rounded bg-[var(--surface)] px-2 py-0.5 text-[11px]" style={{ border: "1px solid var(--line)" }}>
                        {c.zone}: {c.channel}{c.members != null ? ` · ${c.members} ${t("bl.members")}` : ""}
                      </span>
                    ))}
                  </div>
                )}
                {result.channels_posted.length === 0 && result.email.targeted === 0 && (
                  <p className="mt-1 text-[12px] text-[var(--ink-soft)]">{t("bl.channelHint")}</p>
                )}
              </div>
            )}
          </div>
        </section>

        {/* Right: zone channel + email recipients */}
        <div className="space-y-3">
          <section className="panel p-4">
            <SectionTitle>{t("bl.zoneChannels")}</SectionTitle>
            <p className="text-[11px] text-[var(--ink-soft)]">{t("bl.channelHint")}</p>
            <div className="mt-2 flex gap-2">
              <input className="field flex-1" placeholder={t("bl.channelPlaceholder")} value={channelInput} onChange={(e) => setChannelInput(e.target.value)} />
              <button onClick={saveChannel} className="btn btn-ink">{t("bl.setChannel")}</button>
            </div>
            <div className="mt-3 space-y-1">
              {zones.map((z) => (
                <div key={z.id} className="flex items-center gap-2 rounded border border-[var(--line)] px-2.5 py-1.5 text-[12px]">
                  <span className="h-2 w-2 rounded-full" style={{ background: z.telegram_channel ? "var(--ok)" : "var(--line-2)" }} />
                  <span className="font-semibold">{z.name}</span>
                  <span className="mono ml-auto truncate text-[var(--ink-soft)]">{z.telegram_channel ?? t("bl.noChannelSet")}</span>
                  {z.join_link && <a href={z.join_link} target="_blank" rel="noreferrer" className="shrink-0 font-semibold text-[var(--accent-ink)]">{t("bl.join")}</a>}
                </div>
              ))}
            </div>
          </section>

          <section className="panel p-4">
            <SectionTitle hint={`${emailSubs.length} ${t("bl.total")}`}>{t("bl.emailRecipients")}</SectionTitle>
            <p className="text-[11px] text-[var(--ink-soft)]">{t("bl.emailHint")}</p>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <input className="field col-span-2" placeholder={t("bl.addrEmail")} value={email.address} onChange={(e) => setEmail({ ...email, address: e.target.value })} />
              <select className="field" value={email.zone_id} onChange={(e) => setEmail({ ...email, zone_id: e.target.value })}>
                <option value="">{t("bl.noZone")}</option>
                {zones.map((z) => <option key={z.id} value={z.id}>{z.name}</option>)}
              </select>
              <input className="field" placeholder={t("bl.nameOpt")} value={email.name} onChange={(e) => setEmail({ ...email, name: e.target.value })} />
              <button onClick={addEmail} disabled={emailBusy || !email.address.trim()} className="btn btn-ink col-span-2 py-2">
                {emailBusy ? `${t("bl.adding")}…` : `+ ${t("bl.addSub")}`}
              </button>
            </div>
            <div className="mt-3 max-h-48 space-y-1 overflow-y-auto">
              {emailSubs.map((s, i) => {
                const z = zones.find((zz) => zz.id === s.zone_id);
                return (
                  <div key={i} className="flex items-center gap-2 rounded border border-[var(--line)] px-2.5 py-1.5 text-[12px]">
                    <span className="mono grid h-5 w-5 place-items-center rounded bg-[var(--surface-2)] text-[10px] font-bold text-[var(--ink-soft)]">E</span>
                    <span className="truncate font-medium">{s.name || s.address}</span>
                    <span className="ml-auto shrink-0 text-[var(--ink-soft)]">{z?.name ?? "-"}</span>
                  </div>
                );
              })}
              {emailSubs.length === 0 && <p className="text-[12px] text-[var(--ink-soft)]">{t("bl.noSubs")}</p>}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
