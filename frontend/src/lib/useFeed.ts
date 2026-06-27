/** Live feed hook: loads recent reports, then prepends new ones pushed over the
 *  WebSocket. Auto-reconnects. Also exposes a connection indicator. */
import { useEffect, useRef, useState } from "react";
import { api, type Report } from "./api";

export function useFeed(limit = 40) {
  const [reports, setReports] = useState<Report[]>([]);
  const [connected, setConnected] = useState(false);
  const [latestId, setLatestId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let closed = false;
    api.feed(limit).then(setReports).catch(() => {});

    const connect = () => {
      if (closed) return;
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/api/v1/ws/feed`);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) setTimeout(connect, 1500);
      };
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === "report.new") {
            const r = msg.data as Report;
            setReports((prev) => [r, ...prev].slice(0, limit));
            setLatestId(r.id);
          }
        } catch {
          /* ignore */
        }
      };
    };
    connect();

    return () => {
      closed = true;
      wsRef.current?.close();
    };
  }, [limit]);

  return { reports, connected, latestId };
}
