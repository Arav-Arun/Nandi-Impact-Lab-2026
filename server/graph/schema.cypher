// ─────────────────────────────────────────────────────────────────────────────
// NANDI Neo4j schema - node/relationship model + constraints (SoW §5.3).
//
// Applied by scripts/seed_neo4j.py before the topology seed. Uniqueness
// constraints double as lookup indexes, which keeps the runtime MERGE/MATCH in
// the validation queries fast.
//
// NODE TYPES
//   (:MissingReport {id, filed_at, status, last_seen_time})
//   (:FoundReport   {id, found_at, status})
//   (:Person        {ref, name, age, gender, origin_city, language_spoken})
//   (:Zone          {id, name, venue})
//   (:Landmark      {name})
//   (:Booth         {id, name})
//   (:Phone         {number})
//   (:Group         {id, origin_city, origin_state})
//   (:City          {name, state})
//   (:Venue         {name})
//
// RELATIONSHIPS
//   (:MissingReport)-[:DESCRIBES]->(:Person)
//   (:FoundReport)-[:DESCRIBES]->(:Person)
//   (:MissingReport)-[:FILED_AT]->(:Booth)
//   (:FoundReport)-[:REGISTERED_AT]->(:Booth)
//   (:FoundReport)-[:IN_ZONE]->(:Zone)            // fallback location anchor
//   (:Booth)-[:IN_ZONE]->(:Zone)
//   (:Zone)-[:ADJACENT_TO]->(:Zone)               // bidirectional
//   (:Zone)-[:PART_OF]->(:Venue)
//   (:MissingReport)-[:LAST_SEEN_AT]->(:Landmark)
//   (:Landmark)-[:IN_ZONE]->(:Zone)
//   (:Phone)-[:REGISTERED_IN]->(:Zone)
//   (:Phone)-[:BELONGS_TO]->(:Group)
//   (:Person)-[:FROM_CITY]->(:City)
//   (:Group)-[:FROM_CITY]->(:City)
//   (:City)-[:IN_STATE]->(:State)
//   (:MissingReport)-[:MATCHED_TO]->(:FoundReport)  // written on confirm only
//
// NOTE: Person carries a synthetic unique key `ref` ('missing:<id>' /
// 'found:<id>') so the two sides stay distinct nodes until a confirmed match.
// ─────────────────────────────────────────────────────────────────────────────

CREATE CONSTRAINT zone_id        IF NOT EXISTS FOR (z:Zone)          REQUIRE z.id     IS UNIQUE;
CREATE CONSTRAINT booth_id       IF NOT EXISTS FOR (b:Booth)         REQUIRE b.id     IS UNIQUE;
CREATE CONSTRAINT landmark_name  IF NOT EXISTS FOR (l:Landmark)      REQUIRE l.name   IS UNIQUE;
CREATE CONSTRAINT city_name      IF NOT EXISTS FOR (c:City)          REQUIRE c.name   IS UNIQUE;
CREATE CONSTRAINT state_name     IF NOT EXISTS FOR (s:State)         REQUIRE s.name   IS UNIQUE;
CREATE CONSTRAINT venue_name     IF NOT EXISTS FOR (v:Venue)         REQUIRE v.name   IS UNIQUE;
CREATE CONSTRAINT person_ref     IF NOT EXISTS FOR (p:Person)        REQUIRE p.ref    IS UNIQUE;
CREATE CONSTRAINT phone_number   IF NOT EXISTS FOR (ph:Phone)        REQUIRE ph.number IS UNIQUE;
CREATE CONSTRAINT group_id       IF NOT EXISTS FOR (g:Group)         REQUIRE g.id     IS UNIQUE;
CREATE CONSTRAINT missing_id     IF NOT EXISTS FOR (m:MissingReport) REQUIRE m.id     IS UNIQUE;
CREATE CONSTRAINT found_id       IF NOT EXISTS FOR (f:FoundReport)   REQUIRE f.id     IS UNIQUE;
