// landmark_pattern_match - does THIS candidate's (last-seen landmark → found
// booth) flow match a historically common pattern learned from confirmed matches?
//
// Params: $missing_id $found_id $min_times
// Returns one boolean: pattern_match.
//
// This is the per-candidate companion to the dashboard-wide landmark_pattern
// aggregation. It first resolves the candidate's own (from_landmark, to_booth)
// pair, then counts how many PRIOR confirmed matches followed the same flow.

MATCH (m0:MissingReport {id: $missing_id})-[:LAST_SEEN_AT]->(l:Landmark)
MATCH (f0:FoundReport   {id: $found_id})-[:REGISTERED_AT]->(b:Booth)
WITH l.name AS from_landmark, b.name AS to_booth
CALL {
  WITH from_landmark, to_booth
  MATCH (m:MissingReport)-[:LAST_SEEN_AT]->(:Landmark {name: from_landmark})
  MATCH (m)-[:MATCHED_TO]->(:FoundReport)-[:REGISTERED_AT]->(:Booth {name: to_booth})
  RETURN count(*) AS times
}
RETURN (times >= $min_times) AS pattern_match
