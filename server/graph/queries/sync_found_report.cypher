// sync_found_report - idempotently upsert a FoundReport and its satellites.
//
// Params (set by services.neo4j_client.sync_found_report):
//   $id $found_at $status $name $age $gender $origin_city $language
//   $booth_id $zone_id
//
// The registration booth is the found side's location anchor: zone_plausibility
// reads (FoundReport)-[:REGISTERED_AT]->(Booth)-[:IN_ZONE]->(Zone), and the
// learned landmark→booth pattern uses the same booth.

MERGE (f:FoundReport {id: $id})
  SET f.found_at = $found_at,
      f.status   = $status

MERGE (p:Person {ref: 'found:' + $id})
  SET p.name            = $name,
      p.age             = $age,
      p.gender          = $gender,
      p.origin_city     = $origin_city,
      p.language_spoken = $language
MERGE (f)-[:DESCRIBES]->(p)

// Apparent city of origin - only when known.
FOREACH (_ IN CASE WHEN $origin_city IS NULL THEN [] ELSE [1] END |
  MERGE (c:City {name: $origin_city})
  MERGE (p)-[:FROM_CITY]->(c)
)

// Registration booth.
FOREACH (_ IN CASE WHEN $booth_id IS NULL THEN [] ELSE [1] END |
  MERGE (b:Booth {id: $booth_id})
  MERGE (f)-[:REGISTERED_AT]->(b)
)

// Current zone (fallback location anchor when no booth was recorded).
FOREACH (_ IN CASE WHEN $zone_id IS NULL THEN [] ELSE [1] END |
  MERGE (z:Zone {id: $zone_id})
  MERGE (f)-[:IN_ZONE]->(z)
)
