// temporal - is the time gap between last-seen and found plausible?  (SoW §6.1)
//
// Params: $missing_id $found_id
// Returns very_recent (<2h) / same_day (<24h) / stale (>72h).
//
// We use duration.inSeconds(...).seconds / 3600 for the TOTAL hour gap. (The
// literal SoW snippet used `.hours`, which is only the hours *component* of a
// normalised duration and undercounts multi-day gaps - total seconds is correct.)
// Values are NULL when either timestamp is missing, so no temporal modifier fires.

MATCH (m:MissingReport {id: $missing_id})
MATCH (f:FoundReport   {id: $found_id})
WITH
  CASE
    WHEN m.last_seen_time IS NULL OR f.found_at IS NULL THEN null
    ELSE duration.inSeconds(m.last_seen_time, f.found_at).seconds / 3600.0
  END AS gap_hours
RETURN
  CASE WHEN gap_hours IS NULL THEN null ELSE gap_hours < 2  END AS very_recent,
  CASE WHEN gap_hours IS NULL THEN null ELSE gap_hours < 24 END AS same_day,
  CASE WHEN gap_hours IS NULL THEN null ELSE gap_hours > 72 END AS stale
