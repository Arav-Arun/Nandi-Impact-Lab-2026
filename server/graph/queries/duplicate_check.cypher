// duplicate_check — find other ACTIVE missing reports that look like duplicates
// of the one being checked.  (SoW §6.1)
//
// Params: $current_id $name_fragment $age $gender
// Returns duplicate_count and the list of ids.
//
// Heuristic: same gender, age within ±5, and (when a name fragment is supplied)
// a fuzzy name overlap. coalesce() guards keep NULL fields from throwing. An
// empty $name_fragment disables the name constraint (age+gender only).

MATCH (m:MissingReport)-[:DESCRIBES]->(p:Person)
WHERE m.status = 'active'
  AND m.id <> $current_id
  AND abs(coalesce(p.age, -999) - $age) <= 5
  AND coalesce(p.gender, '') = $gender
  AND ($name_fragment = ''
       OR toLower(coalesce(p.name, '')) CONTAINS toLower($name_fragment))
RETURN count(m) AS duplicate_count, collect(m.id) AS ids
