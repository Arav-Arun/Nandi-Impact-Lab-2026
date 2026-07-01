// zone_plausibility - are the found person and the missing person geographically
// consistent?  (SoW §6.1)
//
// Params: $missing_id $found_id
// Returns one row: same_zone / adjacent_zone / same_venue.
//
// Each value is NULL when either side's zone is unknown (so the caller can tell
// "unknown" apart from "known and different" - only the latter sets the
// different_venue penalty). ADJACENT_TO is checked in both directions to be
// robust to how the seed stored the (bidirectional) edge.

MATCH (m:MissingReport {id: $missing_id})
MATCH (f:FoundReport   {id: $found_id})

// Found side: prefer the registration booth's zone, else the directly-linked zone.
OPTIONAL MATCH (f)-[:REGISTERED_AT]->(:Booth)-[:IN_ZONE]->(fzb:Zone)
OPTIONAL MATCH (f)-[:IN_ZONE]->(fzd:Zone)
// Missing side: the last-seen landmark's zone.
OPTIONAL MATCH (m)-[:LAST_SEEN_AT]->(:Landmark)-[:IN_ZONE]->(mz:Zone)

WITH coalesce(fzb, fzd) AS fz, mz
RETURN
  CASE WHEN fz IS NULL OR mz IS NULL THEN null
       ELSE fz.id = mz.id END                                          AS same_zone,
  CASE WHEN fz IS NULL OR mz IS NULL THEN null
       ELSE (EXISTS((mz)-[:ADJACENT_TO]->(fz))
             OR EXISTS((fz)-[:ADJACENT_TO]->(mz))) END                 AS adjacent_zone,
  CASE WHEN fz IS NULL OR mz IS NULL THEN null
       ELSE fz.venue = mz.venue END                                    AS same_venue
