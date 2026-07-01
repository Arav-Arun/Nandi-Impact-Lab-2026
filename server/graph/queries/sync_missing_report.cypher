// sync_missing_report - idempotently upsert a MissingReport and its satellites.
//
// Called by M2's intake (after the SQL row exists) and defensively by the
// matcher. Every clause is MERGE, so offline-sync replays never duplicate.
// Params (set by services.neo4j_client.sync_missing_report):
//   $id $filed_at $status $name $age $gender $origin_city $language
//   $last_seen_time $landmark $zone_id $booth_id $filer_phone
//
// Person is keyed by a synthetic `ref` ('missing:<id>') so a missing-side person
// stays a distinct node from any found-side person until a confirmed MATCHED_TO
// links the two reports.

MERGE (m:MissingReport {id: $id})
  SET m.filed_at       = $filed_at,
      m.status         = $status,
      m.last_seen_time = $last_seen_time

MERGE (p:Person {ref: 'missing:' + $id})
  SET p.name            = $name,
      p.age             = $age,
      p.gender          = $gender,
      p.origin_city     = $origin_city,
      p.language_spoken = $language
MERGE (m)-[:DESCRIBES]->(p)

// City of origin - only when known.
FOREACH (_ IN CASE WHEN $origin_city IS NULL THEN [] ELSE [1] END |
  MERGE (c:City {name: $origin_city})
  MERGE (p)-[:FROM_CITY]->(c)
)

// Last-seen landmark, linked into its zone so zone_plausibility can traverse it.
FOREACH (_ IN CASE WHEN $landmark IS NULL THEN [] ELSE [1] END |
  MERGE (l:Landmark {name: $landmark})
  MERGE (m)-[:LAST_SEEN_AT]->(l)
  FOREACH (__ IN CASE WHEN $zone_id IS NULL THEN [] ELSE [1] END |
    MERGE (z:Zone {id: $zone_id})
    MERGE (l)-[:IN_ZONE]->(z)
  )
)

// Filing booth.
FOREACH (_ IN CASE WHEN $booth_id IS NULL THEN [] ELSE [1] END |
  MERGE (b:Booth {id: $booth_id})
  MERGE (m)-[:FILED_AT]->(b)
)

// Filer's phone - enables the origin-city check via group membership.
FOREACH (_ IN CASE WHEN $filer_phone IS NULL THEN [] ELSE [1] END |
  MERGE (:Phone {number: $filer_phone})
)
