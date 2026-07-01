/** Thin API client for the NANDI intake backend. Unwraps the {data,error} envelope. */

export type Stats = {
  total: number;
  live_today: number;
  by_status: Record<string, number>;
  by_channel: Record<string, number>;
  by_language: Record<string, number>;
  by_age_band: Record<string, number>;
  by_gender: Record<string, number>;
  top_locations: Record<string, number>;
  duplicates: number;
  missing_name_pct: number;
  missing_mobile_pct: number;
  reunited: number;
  avg_resolution_hours: number | null;
  timeseries: { date: string; count: number }[];
  // judge-aligned operational metrics
  cross_center_matches: number;
  duplicate_reports_detected: number;
  cases_missing_name: number;
  cases_missing_mobile: number;
  requires_escalation: number;
  high_risk_unresolved: number;
};

export type Report = {
  id: string;
  case_id: string;
  report_type: string;
  channel: string;
  status: string;
  reported_at: string;
  person_name: string | null;
  gender: string | null;
  age_band: string | null;
  state: string | null;
  district: string | null;
  language: string | null;
  last_seen_location: string | null;
  physical_description: string | null;
  reporter_mobile_masked: string | null;
  reporting_center: string | null;
  is_duplicate_report: boolean;
  detected_language: string | null;
  extraction_confidence: number | null;
  photo_url?: string | null;
  priority?: boolean;   // vulnerable person (child ≤12 / elder ≥70), open case
};

async function unwrap<T>(res: Response): Promise<T> {
  const body = await res.json();
  if (body.error) throw new Error(body.error.message || body.error.code);
  return body.data as T;
}

export type Booth = { id: string; name: string; zone: string | null };

export type MatchCandidate = {
  missing_id: string;
  subject_name: string | null;
  subject_age: number | null;
  subject_gender: string | null;
  physical_description: string;
  last_seen_landmark: string | null;
  filed_at: string;
  origin_city: string | null;
  vector_score: number;
  confidence: number;
  band: "high" | "probable" | "possible";
  reasons: string[];
  photo_url?: string | null;
};

export type ConfirmResult = {
  matched: boolean;
  otp: string;
  notified: boolean;
  notify_channel: "telegram" | "onscreen";
  booth_name: string | null;
  zone_name: string | null;
};

export type ReuniteResult = {
  found_id: string;
  missing_id: string;
  reunited: boolean;
  detail: string | null;
};

export const api = {
  health: () => fetch("/health").then((r) => unwrap<any>(r)),
  stats: () => fetch("/api/v1/stats").then((r) => unwrap<Stats>(r)),
  feed: (limit = 40) => fetch(`/api/v1/feed?limit=${limit}`).then((r) => unwrap<Report[]>(r)),
  booths: () => fetch("/api/v1/booths").then((r) => unwrap<Booth[]>(r)),
  fileMissing: (payload: Record<string, unknown>) =>
    fetch("/api/v1/intake/missing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then((r) => unwrap<{ id: string; case_id: string }>(r)),

  fileFound: (payload: Record<string, unknown>) =>
    fetch("/api/v1/intake/found", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then((r) => unwrap<{ found_id: string; case_id: string; status: string }>(r)),

  match: (foundId: string) =>
    fetch(`/api/v1/match/${foundId}`).then((r) =>
      unwrap<{ found_id: string; candidates: MatchCandidate[] }>(r)
    ),

  matchConfirm: (foundId: string, missingId: string, boothId: string, operatorId?: string) =>
    fetch("/api/v1/match/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Booth-ID": boothId },
      body: JSON.stringify({ found_id: foundId, missing_id: missingId, operator_id: operatorId }),
    }).then((r) => unwrap<ConfirmResult>(r)),

  matchReunite: (foundId: string, missingId: string, boothId: string, otp: string, operatorId?: string) =>
    fetch("/api/v1/match/reunite", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Booth-ID": boothId },
      body: JSON.stringify({ found_id: foundId, missing_id: missingId, otp, operator_id: operatorId }),
    }).then((r) => unwrap<ReuniteResult>(r)),

  matchReject: (foundId: string, boothId: string, rejected: string[], operatorId?: string) =>
    fetch("/api/v1/match/reject", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Booth-ID": boothId },
      body: JSON.stringify({ found_id: foundId, rejected_missing_ids: rejected, operator_id: operatorId }),
    }).then((r) => unwrap<{ found_id: string; status: string }>(r)),

  transcribe: (blob: Blob) => {
    const fd = new FormData();
    fd.append("file", blob, "voice.webm");
    return fetch("/api/v1/media/transcribe", { method: "POST", body: fd }).then((r) =>
      unwrap<Transcription>(r)
    );
  },

  uploadPhoto: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch("/api/v1/media/upload", { method: "POST", body: fd }).then((r) =>
      unwrap<{ photo_url: string; description: string | null }>(r)
    );
  },

  extract: (text: string, detected_language?: string | null) =>
    fetch("/api/v1/intake/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, detected_language }),
    }).then((r) => unwrap<Extracted>(r)),

  // ── Blast / escalation + subscribers ──────────────────────────────────────
  channels: () => fetch("/api/v1/channels").then((r) => unwrap<Channels>(r)),

  zones: () => fetch("/api/v1/zones").then((r) => unwrap<Zone[]>(r)),

  subscribers: (zoneId?: string) =>
    fetch(`/api/v1/subscribers${zoneId ? `?zone_id=${zoneId}` : ""}`).then((r) =>
      unwrap<SubscribersResult>(r)
    ),

  addSubscriber: (payload: {
    channel: string;
    address: string;
    zone_id?: string | null;
    name?: string | null;
    language?: string | null;
  }) =>
    fetch("/api/v1/subscribers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then((r) => unwrap<{ id: string; channel: string }>(r)),

  blastZone: (zoneId: string, message: string, subject?: string, channels?: string[]) =>
    fetch("/api/v1/blast/zone", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ zone_id: zoneId, message, subject, channels }),
    }).then((r) => unwrap<BlastResult>(r)),

  blastFound: (foundId: string) =>
    fetch(`/api/v1/blast/found/${foundId}`, { method: "POST" }).then((r) =>
      unwrap<BlastResult>(r)
    ),

  setZoneChannel: (zoneId: string, telegram_channel: string | null) =>
    fetch(`/api/v1/zones/${zoneId}/channel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ telegram_channel }),
    }).then((r) => unwrap<{ id: string; telegram_channel: string | null; join_link: string | null }>(r)),
};

export type Channels = { telegram: boolean; email: boolean };

export type Zone = {
  id: string;
  name: string;
  venue: string;
  display_name_marathi: string;
  color_code: string;
  telegram_channel: string | null;
  join_link: string | null;
  subscribers: number;
  registrants: number;
  reachable: number;
};

export type Subscriber = {
  channel: string;
  address: string;
  zone_id: string | null;
  name: string | null;
};

export type SubscribersResult = {
  by_channel: Record<string, number>;
  total: number;
  subscribers: Subscriber[];
};

export type BlastResult = {
  zones: string[];
  channels_posted: { zone: string; channel: string; sent: boolean; members: number | null }[];
  email: { targeted: number; sent: number };
  targeted: number;
};

export type Transcription = {
  transcript: string;
  language_code: string | null;
  language_name: string | null;
  language_probability: number;
  mock: boolean;
};

export type Extracted = {
  person_name: string | null;
  gender: string | null;
  age_band: string | null;
  age_years: number | null;
  state: string | null;
  district: string | null;
  language: string | null;
  last_seen_location: string | null;
  physical_description: string | null;
  reporter_relation: string | null;
  reporter_mobile: string | null;
  missing_fields: string[];
  confidence: number;
};
