// origin_city - do the missing and found persons share a city / state of origin?
// (SoW §6.1)
//
// Params: $missing_id $found_id $filer_phone
// Returns same_city / same_state (NULL when either side's origin is unknown).
//
// The "missing side" origin is taken from the missing person's own city, falling
// back to the filer's travel-group city (people travel in village/bus groups, so
// the group's origin is a strong signal). Compared against the found person's
// apparent city of origin.

MATCH (m:MissingReport {id: $missing_id})
MATCH (f:FoundReport   {id: $found_id})

OPTIONAL MATCH (m)-[:DESCRIBES]->(pm:Person)-[:FROM_CITY]->(cm:City)
OPTIONAL MATCH (f)-[:DESCRIBES]->(pf:Person)-[:FROM_CITY]->(cf:City)
OPTIONAL MATCH (:Phone {number: $filer_phone})-[:BELONGS_TO]->(:Group)-[:FROM_CITY]->(cg:City)

WITH
  coalesce(cm.name,  cg.name)  AS m_city,
  coalesce(cm.state, cg.state) AS m_state,
  cf
RETURN
  CASE WHEN m_city IS NULL OR cf IS NULL THEN null
       ELSE m_city = cf.name END                       AS same_city,
  CASE WHEN m_state IS NULL OR cf IS NULL THEN null
       ELSE m_state = cf.state END                     AS same_state
