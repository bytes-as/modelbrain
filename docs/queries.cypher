// ModelBrain v3: core Cypher for FalkorDB.
// Graph "hub" holds public facts; graphs "tenant_<slug>" and "sbx_<id>" hold one company each.
// All parameters are passed with falkordb-py: graph.query(q, params) / graph.ro_query(q, params).
// Known FalkorDB caveat: reference every relationship alias you bind, or counts can be wrong.
// Verified against falkordb/falkordb:latest on 18 Oct 2026 (redis-cli GRAPH.QUERY with CYPHER params):
//   *0..6 zero-length paths work; algo.WCC({nodeLabels, relationshipTypes}) YIELD node, componentId works;
//   GRAPH.COPY <src> <dst> works (fails if dst exists); MERGE ... ON CREATE/ON MATCH works;
//   list predicates all(), list comprehensions, labels(), map literals in collect() work.

// ---------------------------------------------------------------------------
// SCHEMA (hub)
// ---------------------------------------------------------------------------
CREATE INDEX FOR (m:Model) ON (m.id);
CREATE INDEX FOR (l:License) ON (l.key);
CREATE INDEX FOR (c:Clause) ON (c.id);
CREATE INDEX FOR (f:Fingerprint) ON (f.key);
CREATE INDEX FOR (s:Snapshot) ON (s.id);

// SCHEMA (tenant graphs)
CREATE INDEX FOR (d:Deployment) ON (d.id);
CREATE INDEX FOR (r:Ruling) ON (r.id);
CREATE INDEX FOR (f:Fact) ON (f.model_id);
CREATE INDEX FOR (t:Task) ON (t.id);
CREATE INDEX FOR (p:Person) ON (p.id);

// ---------------------------------------------------------------------------
// INGEST (Scout) - hub
// ---------------------------------------------------------------------------

// I1: upsert a model's current state
MERGE (m:Model {id: $id})
SET m.sha = $sha, m.declared_license = $declared_license, m.pipeline_tag = $pipeline_tag,
    m.created_at = $created_at, m.last_modified = $last_modified, m.gated = $gated,
    m.is_root = $is_root, m.multimodal = $multimodal, m.ingested_at = $now,
    m.card_has_llama_notice = $card_has_llama_notice, m.has_license_file = $has_license_file,
    m.name_starts_with = $name_starts_with
RETURN m.id;

// I2: record an observed revision (append-only history)
MATCH (m:Model {id: $id})
MERGE (s:Snapshot {id: $snapshot_id})
ON CREATE SET s.model_id = $id, s.sha = $sha, s.declared_license = $declared_license, s.observed_at = $now
MERGE (m)-[:OBSERVED]->(s);

// I3: replace the declared licence (history lives in Snapshot nodes)
MATCH (m:Model {id: $id})
OPTIONAL MATCH (m)-[old:DECLARES]->(:License)
DELETE old;
MATCH (m:Model {id: $id})
MERGE (l:License {key: $license_key})
MERGE (m)-[d:DECLARES]->(l)
SET d.as_of_sha = $sha;

// I4: upsert a declared parent edge (never downgrades a higher tier)
MATCH (c:Model {id: $child})
MERGE (p:Model {id: $parent})
MERGE (c)-[e:DERIVED_FROM]->(p)
ON CREATE SET e.relation = $relation, e.source = 'declared', e.conf = 1.0, e.tier = 2,
              e.evidence = 'card/tags', e.confirmations = 0, e.confirmers = []
ON MATCH SET e.relation = $relation, e.source = 'declared', e.conf = 1.0,
             e.tier = CASE WHEN e.tier < 2 THEN 2 ELSE e.tier END;

// I5: attach a fingerprint
MERGE (f:Fingerprint {key: $key})
ON CREATE SET f.kind = $kind, f.value = $value
WITH f
MATCH (m:Model {id: $model_id})
MERGE (m)-[:HAS_FP]->(f);

// ---------------------------------------------------------------------------
// VERDICT (Auditor) - hub, read-only
// ---------------------------------------------------------------------------

// Q1: every licence and clause inherited along every bounded ancestry path, at a minimum trust tier
MATCH p = (m:Model {id: $model_id})-[:DERIVED_FROM*0..6]->(a:Model)
WHERE all(r IN relationships(p) WHERE r.tier >= $min_tier)
OPTIONAL MATCH (a)-[d:DECLARES]->(l:License)
OPTIONAL MATCH (l)-[i:IMPOSES]->(c:Clause)
RETURN a.id AS ancestor, a.is_root AS is_root, a.multimodal AS multimodal, length(p) AS hops,
       [n IN nodes(p) | n.id] AS path,
       [r IN relationships(p) | r.tier] AS tiers,
       [r IN relationships(p) | r.relation] AS relations,
       l.key AS license,
       collect(CASE WHEN c IS NULL THEN null ELSE
                {id: c.id, kind: c.kind, effect: c.effect, applies_when: c.applies_when,
                 check: c.check, quote: c.quote, source_url: c.source_url, section: c.section} END) AS clauses
ORDER BY hops;

// Q2: lineage completeness - the top of each path; a non-root top means lineage is incomplete
MATCH p = (m:Model {id: $model_id})-[:DERIVED_FROM*0..6]->(a:Model)
WHERE all(r IN relationships(p) WHERE r.tier >= $min_tier)
WITH DISTINCT a
OPTIONAL MATCH (a)-[up:DERIVED_FROM]->(:Model)
WITH a, sum(CASE WHEN up IS NOT NULL AND up.tier >= $min_tier THEN 1 ELSE 0 END) AS ups
WHERE ups = 0
RETURN a.id AS top, coalesce(a.is_root, false) AS is_root, a.declared_license AS declared_license;

// Q3: lineage for the graph view (nodes and edges)
MATCH p = (m:Model {id: $model_id})-[:DERIVED_FROM*0..6]->(a:Model)
WHERE all(r IN relationships(p) WHERE r.tier >= $min_tier)
UNWIND relationships(p) AS e
WITH DISTINCT e
MATCH (c:Model)-[e]->(q:Model)
RETURN DISTINCT c.id AS child, q.id AS parent, e.relation AS relation, e.source AS source, e.tier AS tier, e.conf AS conf,
       c.declared_license AS child_license, q.declared_license AS parent_license;

// ---------------------------------------------------------------------------
// RESOLVER - hub
// ---------------------------------------------------------------------------

// R1: connected components over shared fingerprints (FalkorDB algo.WCC)
CALL algo.WCC({nodeLabels: ['Model', 'Fingerprint'], relationshipTypes: ['HAS_FP']})
YIELD node, componentId
WITH componentId, collect(node) AS ns
WITH componentId, [n IN ns WHERE 'Model' IN labels(n) | n.id] AS model_ids
WHERE size(model_ids) > 1
RETURN componentId, model_ids;

// R2: candidate parents for a model that declares none
MATCH (m:Model {id: $model_id})-[:HAS_FP]->(f:Fingerprint)<-[:HAS_FP]-(r:Model)
WHERE r.is_root = true AND r.id <> m.id
RETURN r.id AS root, collect(DISTINCT f.kind) AS shared_kinds, r.created_at AS created_at
ORDER BY size(shared_kinds) DESC, created_at ASC
LIMIT 5;

// R3: write an inferred edge (MERGE never overwrites an existing declared edge)
MATCH (c:Model {id: $child}), (p:Model {id: $parent})
MERGE (c)-[e:DERIVED_FROM]->(p)
ON CREATE SET e.relation = $relation, e.source = 'inferred', e.conf = $conf, e.tier = $tier,
              e.evidence = $evidence, e.confirmations = 0, e.confirmers = []
RETURN e.tier AS tier, e.source AS source;

// ---------------------------------------------------------------------------
// FAN-OUT (Watcher) - hub
// ---------------------------------------------------------------------------

// D1: every descendant of a changed model
MATCH (src:Model {id: $model_id})<-[:DERIVED_FROM*1..6]-(d:Model)
RETURN DISTINCT d.id AS id, d.declared_license AS declared_license;

// D2: fix leverage - how many descendants did not inherit an upstream notice fix
MATCH (src:Model {id: $model_id})<-[:DERIVED_FROM*1..6]-(d:Model)
WITH DISTINCT d
RETURN count(d) AS descendants,
       sum(CASE WHEN coalesce(d.card_has_llama_notice, false) THEN 0 ELSE 1 END) AS not_inherited;

// D3: author confirmed a parent (card now declares it): promote to tier 4
MATCH (c:Model {id: $child})-[e:DERIVED_FROM]->(p:Model {id: $parent})
SET e.tier = 4, e.source = 'declared', e.evidence = $evidence
RETURN e.tier;

// ---------------------------------------------------------------------------
// COMPOUNDING (Publisher) - hub
// ---------------------------------------------------------------------------

// P1: add a salted tenant hash as a confirmer; promote to tier 3 at two independent confirmers
MATCH (c:Model {id: $child})-[e:DERIVED_FROM]->(p:Model {id: $parent})
WITH e, coalesce(e.confirmers, []) AS cs0
WITH e, CASE WHEN $tenant_hash IN cs0 THEN cs0 ELSE cs0 + [$tenant_hash] END AS cs
SET e.confirmers = cs, e.confirmations = size(cs),
    e.tier = CASE WHEN size(cs) >= 2 AND e.tier < 3 THEN 3 ELSE e.tier END
RETURN e.tier AS tier, e.confirmations AS confirmations;

// ---------------------------------------------------------------------------
// TENANT GRAPHS (Auditor, Watcher, task handoffs)
// ---------------------------------------------------------------------------

// T1: write a ruling and the facts it rests on (append-only; never update a ruling)
MATCH (dep:Deployment {id: $deployment_id})
CREATE (r:Ruling {id: $ruling_id, verdict: $verdict, strict: $strict, created_at: $now,
                  explanation: $explanation, hub_sha_set: $hub_sha_set})
CREATE (r)-[:FOR]->(dep)
WITH r
UNWIND $facts AS fx
CREATE (f:Fact {id: fx.id, model_id: fx.model_id, sha: fx.sha, license_key: fx.license_key,
                clause_ids: fx.clause_ids, edge_tiers: fx.edge_tiers})
CREATE (r)-[:RESTS_ON]->(f)
RETURN count(f) AS facts;

// T2: link a new ruling to the one it replaces
MATCH (new:Ruling {id: $new_id}), (old:Ruling {id: $old_id})
CREATE (new)-[:SUPERSEDES]->(old);

// T3: active rulings that rest on any changed model, with the deployment owner
MATCH (r:Ruling)-[:RESTS_ON]->(f:Fact)
WHERE f.model_id IN $model_ids
OPTIONAL MATCH (newer:Ruling)-[s:SUPERSEDES]->(r)
WITH r, f, newer, s
WHERE newer IS NULL
MATCH (r)-[fr:FOR]->(dep:Deployment)<-[o:OWNS]-(owner:Person)
RETURN r.id AS ruling_id, dep.id AS deployment_id, owner.id AS owner_id,
       collect(DISTINCT f.model_id) AS affected_models;

// T4: reopen a ruling and hand a review task to its owner
MATCH (r:Ruling {id: $ruling_id}), (p:Person {id: $owner_id})
CREATE (e:Event {id: $event_id, kind: 'REOPENED', at: $now, reason: $reason})
CREATE (e)-[:ON]->(r)
CREATE (t:Task {id: $task_id, kind: 'REVIEW_RULING', state: 'OPEN', created_by_agent: 'watcher', created_at: $now})
CREATE (t)-[:ABOUT]->(r)
CREATE (t)-[:ASSIGNED_TO]->(p);

// T5: claim a task with a lease (stale leases return to the pool)
MATCH (t:Task {id: $task_id})
WHERE t.state = 'OPEN' OR (t.state = 'CLAIMED' AND t.lease_until < $now)
SET t.state = 'CLAIMED', t.lease_until = $now + 120000, t.claimed_by = $agent
RETURN t.id AS claimed;

// T6: latest ruling per deployment (the "current knowledge" view for Track 3)
MATCH (prod:Product)-[:RUNS]->(dep:Deployment)<-[:FOR]-(r:Ruling)
OPTIONAL MATCH (newer:Ruling)-[s:SUPERSEDES]->(r)
WITH prod, dep, r, newer, s
WHERE newer IS NULL
OPTIONAL MATCH (dep)<-[o:OWNS]-(owner:Person)
RETURN prod.name AS product, dep.model_id AS model, r.verdict AS verdict, r.created_at AS decided_at,
       owner.name AS owner, r.id AS ruling_id;

// T7: decision trace - why did we decide this, and who signed it
MATCH (r:Ruling {id: $ruling_id})-[ro:RESTS_ON]->(f:Fact)
OPTIONAL MATCH (e:Event)-[on:ON]->(r)
OPTIONAL MATCH (p:Person)-[sg:SIGNED]->(e)
RETURN r.verdict AS verdict,
       collect(DISTINCT {model_id: f.model_id, sha: f.sha, license_key: f.license_key, clause_ids: f.clause_ids}) AS facts,
       collect(DISTINCT {kind: e.kind, at: e.at, by: p.name}) AS events;

// ---------------------------------------------------------------------------
// GRAPH ALGORITHMS AS AGENT TOOLS - hub (all verified on falkordb/falkordb:latest, 18 Oct 2026)
// These are exposed to agents as MCP tools and drive UI panels. Keep them bounded and read-only.
// ---------------------------------------------------------------------------

// A1: relabel hubs - models whose declared licence differs from what they inherit, ranked by PageRank
// over DERIVED_FROM (child -> parent). Requires Model.declared_differs, set by the Auditor batch (G-list).
CALL algo.pageRank('Model', 'DERIVED_FROM') YIELD node, score
WITH node, score
WHERE node.declared_differs = true
RETURN node.id AS model, score
ORDER BY score DESC
LIMIT 20;

// A2: chokepoints - models that sit between many others (a fix here reaches the most descendants)
CALL algo.betweenness({nodeLabels: ['Model'], relationshipTypes: ['DERIVED_FROM'], samplingSize: 64})
YIELD node, score
RETURN node.id AS model, score
ORDER BY score DESC
LIMIT 20;

// A3: model families - community detection over lineage, for the hub explorer view
CALL algo.labelPropagation({nodeLabels: ['Model'], relationshipTypes: ['DERIVED_FROM'], maxIterations: 10})
YIELD node, communityId
WITH communityId, collect(node.id) AS models
WHERE size(models) > 1
RETURN communityId, size(models) AS size, models[0..10] AS sample
ORDER BY size DESC
LIMIT 50;

// A4: shortest proof path from a model to the root that carries a licence (used by explain);
// a NULL path is the "no path" proof that the model does not descend from that root.
MATCH (m:Model {id: $model_id}), (r:Model {id: $root_id})
WITH shortestPath((m)-[:DERIVED_FROM*1..6]->(r)) AS p
RETURN p IS NULL AS no_path,
       CASE WHEN p IS NULL THEN [] ELSE [n IN nodes(p) | n.id] END AS path,
       CASE WHEN p IS NULL THEN 0 ELSE length(p) END AS hops;

// A5: all bounded ancestry paths via the single-source paths algorithm (alternative to Q1's MATCH)
MATCH (m:Model {id: $model_id})
CALL algo.SSpaths({sourceNode: m, relTypes: ['DERIVED_FROM'], maxLen: 6, pathCount: 50})
YIELD path, pathWeight
RETURN [n IN nodes(path) | n.id] AS path, length(path) AS hops
LIMIT 50;

// ---------------------------------------------------------------------------
// HOSTED PATH (OpenRouter catalogue) - hub. Add-on, see BLUEPRINT section 18.
// ---------------------------------------------------------------------------

// O1: upsert an inference provider from GET https://openrouter.ai/api/v1/providers
MERGE (p:Provider {slug: $slug})
SET p.name = $name, p.hq = $hq, p.datacenters = $datacenters,
    p.tos_url = $tos_url, p.privacy_url = $privacy_url, p.updated_at = $now;

// O2: upsert a hosted model and link it to its Hugging Face weights (hugging_face_id)
MERGE (h:HostedModel {id: $or_id})
SET h.name = $name, h.updated_at = $now
WITH h
MERGE (m:Model {id: $hf_id})
MERGE (h)-[:IS]->(m);

// O3: a provider serves a hosted model (from GET /api/v1/models/{author}/{slug}/endpoints)
MATCH (h:HostedModel {id: $or_id})
MERGE (p:Provider {slug: $provider_slug})
MERGE (p)-[s:SERVES]->(h)
SET s.quantization = $quantization, s.tag = $tag, s.status = $status, s.uptime_30m = $uptime_30m;

// O4: providers that can serve a hosted model from allowed datacenter countries.
// No rows is the "no resident provider" proof.
MATCH (h:HostedModel {id: $or_id})<-[s:SERVES]-(p:Provider)
WHERE any(dc IN coalesce(p.datacenters, []) WHERE dc IN $allowed_countries)
RETURN p.slug AS provider, p.name AS name, p.hq AS hq, p.datacenters AS datacenters,
       s.quantization AS quantization, s.uptime_30m AS uptime
ORDER BY uptime DESC;

// O5: the weights behind a hosted model (then run Q1/Q2 on m.id)
MATCH (h:HostedModel {id: $or_id})-[:IS]->(m:Model)
RETURN m.id AS hf_id;

// ---------------------------------------------------------------------------
// LICENCE TEXT WATCH - hub + tenants. Add-on, see BLUEPRINT section 18.
// ---------------------------------------------------------------------------

// L1: record a fetched licence text version (append-only) and link the clauses it backs
MERGE (t:LicenseText {id: $text_id})
ON CREATE SET t.url = $url, t.sha = $sha, t.fetched_at = $now
WITH t
UNWIND $clause_ids AS cid
MATCH (c:Clause {id: cid})
MERGE (c)-[:FROM_TEXT]->(t);

// L2: latest known text sha per source URL (to detect a change)
MATCH (t:LicenseText {url: $url})
RETURN t.sha AS sha, t.fetched_at AS fetched_at
ORDER BY fetched_at DESC
LIMIT 1;

// T8: (tenant graph) active rulings that rest on any changed clause
MATCH (r:Ruling)-[:RESTS_ON]->(f:Fact)
WHERE any(c IN f.clause_ids WHERE c IN $clause_ids)
OPTIONAL MATCH (newer:Ruling)-[s:SUPERSEDES]->(r)
WITH r, f, newer, s
WHERE newer IS NULL
MATCH (r)-[fr:FOR]->(dep:Deployment)<-[o:OWNS]-(owner:Person)
RETURN DISTINCT r.id AS ruling_id, dep.id AS deployment_id, owner.id AS owner_id;
