// landmark_pattern — learned "last-seen landmark → typically-found booth" flows,
// aggregated across all confirmed matches.  (SoW §6.1, dashboard Panel 4)
//
// Params: $min_times $limit
// Returns rows: from_landmark, to_landmark (the found booth), times.
//
// Powers the daily volunteer-redeployment briefing, e.g. "People last seen near
// Ramkund Ghat typically turn up at Panchavati Booth 3." Consumed by M3's
// GET /dashboard/patterns via services.neo4j_client.landmark_patterns().

MATCH (m:MissingReport)-[:LAST_SEEN_AT]->(l:Landmark)
MATCH (m)-[:MATCHED_TO]->(:FoundReport)-[:REGISTERED_AT]->(b:Booth)
WITH l.name AS from_landmark, b.name AS to_landmark, count(*) AS times
WHERE times >= $min_times
RETURN from_landmark, to_landmark, times
ORDER BY times DESC
LIMIT $limit
