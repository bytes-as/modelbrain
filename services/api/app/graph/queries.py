"""Cypher copied from docs/queries.cypher. Do not edit by hand; keep the sync test green."""

SCHEMA = """
CREATE INDEX FOR (m:Model) ON (m.id);
CREATE INDEX FOR (l:License) ON (l.key);
CREATE INDEX FOR (c:Clause) ON (c.id);
CREATE INDEX FOR (f:Fingerprint) ON (f.key);
CREATE INDEX FOR (s:Snapshot) ON (s.id);

CREATE INDEX FOR (d:Deployment) ON (d.id);
CREATE INDEX FOR (r:Ruling) ON (r.id);
CREATE INDEX FOR (f:Fact) ON (f.model_id);
CREATE INDEX FOR (t:Task) ON (t.id);
CREATE INDEX FOR (p:Person) ON (p.id);
"""

I1 = """
MERGE (m:Model {id: $id})
SET m.sha = $sha, m.declared_license = $declared_license, m.pipeline_tag = $pipeline_tag,
    m.created_at = $created_at, m.last_modified = $last_modified, m.gated = $gated,
    m.is_root = $is_root, m.multimodal = $multimodal, m.ingested_at = $now,
    m.card_has_llama_notice = $card_has_llama_notice, m.has_license_file = $has_license_file,
    m.name_starts_with = $name_starts_with
RETURN m.id;
"""

I2 = """
MATCH (m:Model {id: $id})
MERGE (s:Snapshot {id: $snapshot_id})
ON CREATE SET s.model_id = $id, s.sha = $sha, s.declared_license = $declared_license, s.observed_at = $now
MERGE (m)-[:OBSERVED]->(s);
"""

I3 = """
MATCH (m:Model {id: $id})
OPTIONAL MATCH (m)-[old:DECLARES]->(:License)
DELETE old;
MATCH (m:Model {id: $id})
MERGE (l:License {key: $license_key})
MERGE (m)-[d:DECLARES]->(l)
SET d.as_of_sha = $sha;
"""

I4 = """
MATCH (c:Model {id: $child})
MERGE (p:Model {id: $parent})
MERGE (c)-[e:DERIVED_FROM]->(p)
ON CREATE SET e.relation = $relation, e.source = 'declared', e.conf = 1.0, e.tier = 2,
              e.evidence = 'card/tags', e.confirmations = 0, e.confirmers = []
ON MATCH SET e.relation = $relation, e.source = 'declared', e.conf = 1.0,
             e.tier = CASE WHEN e.tier < 2 THEN 2 ELSE e.tier END;
"""

I5 = """
MERGE (f:Fingerprint {key: $key})
ON CREATE SET f.kind = $kind, f.value = $value
WITH f
MATCH (m:Model {id: $model_id})
MERGE (m)-[:HAS_FP]->(f);
"""

Q1 = """
MATCH p = (m:Model {id: $model_id})-[:DERIVED_FROM*0..6]->(a:Model)
WHERE all(r IN relationships(p) WHERE r.tier >= $min_tier)
OPTIONAL MATCH (a)-[d:DECLARES]->(l:License)
OPTIONAL MATCH (l)-[i:IMPOSES]->(c:Clause)
RETURN a.id AS ancestor, a.is_root AS is_root, a.multimodal AS multimodal, length(p) AS hops,
       [n IN nodes(p) | n.id] AS path,
       [r IN relationships(p) | r.tier] AS tiers,
       [r IN relationships(p) | r.relation] AS relations,
       [r IN relationships(p) | r.method] AS methods,
       [r IN relationships(p) | r.weights_sim] AS weights_sims,
       [r IN relationships(p) | r.share] AS shares,
       l.key AS license,
       collect(CASE WHEN c IS NULL THEN null ELSE
                {id: c.id, kind: c.kind, effect: c.effect, applies_when: c.applies_when,
                 check: c.check, quote: c.quote, source_url: c.source_url, section: c.section} END) AS clauses
ORDER BY hops;
"""

Q2 = """
MATCH p = (m:Model {id: $model_id})-[:DERIVED_FROM*0..6]->(a:Model)
WHERE all(r IN relationships(p) WHERE r.tier >= $min_tier)
WITH DISTINCT a
OPTIONAL MATCH (a)-[up:DERIVED_FROM]->(:Model)
WITH a, sum(CASE WHEN up IS NOT NULL AND up.tier >= $min_tier THEN 1 ELSE 0 END) AS ups
WHERE ups = 0
RETURN a.id AS top, coalesce(a.is_root, false) AS is_root, a.declared_license AS declared_license;
"""

Q3 = """
MATCH p = (m:Model {id: $model_id})-[:DERIVED_FROM*0..6]->(a:Model)
WHERE all(r IN relationships(p) WHERE r.tier >= $min_tier)
UNWIND relationships(p) AS e
WITH DISTINCT e
MATCH (c:Model)-[e]->(q:Model)
RETURN DISTINCT c.id AS child, q.id AS parent, e.relation AS relation, e.source AS source, e.tier AS tier, e.conf AS conf,
       c.declared_license AS child_license, q.declared_license AS parent_license;
"""

R1 = """
CALL algo.WCC({nodeLabels: ['Model', 'Fingerprint'], relationshipTypes: ['HAS_FP']})
YIELD node, componentId
WITH componentId, collect(node) AS ns
WITH componentId, [n IN ns WHERE 'Model' IN labels(n) | n.id] AS model_ids
WHERE size(model_ids) > 1
RETURN componentId, model_ids;
"""

R2 = """
MATCH (m:Model {id: $model_id})-[:HAS_FP]->(f:Fingerprint)<-[:HAS_FP]-(r:Model)
WHERE r.is_root = true AND r.id <> m.id
RETURN r.id AS root, collect(DISTINCT f.kind) AS shared_kinds, r.created_at AS created_at
ORDER BY size(shared_kinds) DESC, created_at ASC
LIMIT 5;
"""

R3 = """
MATCH (c:Model {id: $child}), (p:Model {id: $parent})
MERGE (c)-[e:DERIVED_FROM]->(p)
ON CREATE SET e.relation = $relation, e.source = 'inferred', e.conf = $conf, e.tier = $tier,
              e.evidence = $evidence, e.confirmations = 0, e.confirmers = []
RETURN e.tier AS tier, e.source AS source;
"""

D1 = """
MATCH (src:Model {id: $model_id})<-[:DERIVED_FROM*1..6]-(d:Model)
RETURN DISTINCT d.id AS id, d.declared_license AS declared_license;
"""

D2 = """
MATCH (src:Model {id: $model_id})<-[:DERIVED_FROM*1..6]-(d:Model)
WITH DISTINCT d
RETURN count(d) AS descendants,
       sum(CASE WHEN coalesce(d.card_has_llama_notice, false) THEN 0 ELSE 1 END) AS not_inherited;
"""

D3 = """
MATCH (c:Model {id: $child})-[e:DERIVED_FROM]->(p:Model {id: $parent})
SET e.tier = 4, e.source = 'declared', e.evidence = $evidence
RETURN e.tier;
"""

P1 = """
MATCH (c:Model {id: $child})-[e:DERIVED_FROM]->(p:Model {id: $parent})
WITH e, coalesce(e.confirmers, []) AS cs0
WITH e, CASE WHEN $tenant_hash IN cs0 THEN cs0 ELSE cs0 + [$tenant_hash] END AS cs
SET e.confirmers = cs, e.confirmations = size(cs),
    e.tier = CASE WHEN size(cs) >= 2 AND e.tier < 3 THEN 3 ELSE e.tier END
RETURN e.tier AS tier, e.confirmations AS confirmations;
"""

T1 = """
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
"""

T2 = """
MATCH (new:Ruling {id: $new_id}), (old:Ruling {id: $old_id})
CREATE (new)-[:SUPERSEDES]->(old);
"""

T3 = """
MATCH (r:Ruling)-[:RESTS_ON]->(f:Fact)
WHERE f.model_id IN $model_ids
OPTIONAL MATCH (newer:Ruling)-[s:SUPERSEDES]->(r)
WITH r, f, newer, s
WHERE newer IS NULL
MATCH (r)-[fr:FOR]->(dep:Deployment)<-[o:OWNS]-(owner:Person)
RETURN r.id AS ruling_id, dep.id AS deployment_id, owner.id AS owner_id,
       collect(DISTINCT f.model_id) AS affected_models;
"""

T4 = """
MATCH (r:Ruling {id: $ruling_id}), (p:Person {id: $owner_id})
CREATE (e:Event {id: $event_id, kind: 'REOPENED', at: $now, reason: $reason})
CREATE (e)-[:ON]->(r)
CREATE (t:Task {id: $task_id, kind: 'REVIEW_RULING', state: 'OPEN', created_by_agent: 'watcher', created_at: $now})
CREATE (t)-[:ABOUT]->(r)
CREATE (t)-[:ASSIGNED_TO]->(p);
"""

T5 = """
MATCH (t:Task {id: $task_id})
WHERE t.state = 'OPEN' OR (t.state = 'CLAIMED' AND t.lease_until < $now)
SET t.state = 'CLAIMED', t.lease_until = $now + 120000, t.claimed_by = $agent
RETURN t.id AS claimed;
"""

T9 = """
MATCH (c:Company)
RETURN c.slug AS slug, c.name AS name, c.hq_country AS hq_country, c.eu AS eu, c.mau AS mau;
"""

T10 = """
MATCH (prod:Product)-[:RUNS]->(dep:Deployment)
OPTIONAL MATCH (dep)<-[:OWNS]-(owner:Person)
RETURN prod.id AS product_id, prod.name AS product, dep.id AS deployment_id,
       dep.model_id AS model, owner.name AS owner;
"""

T6 = """
MATCH (prod:Product)-[:RUNS]->(dep:Deployment)<-[:FOR]-(r:Ruling)
OPTIONAL MATCH (newer:Ruling)-[s:SUPERSEDES]->(r)
WITH prod, dep, r, newer, s
WHERE newer IS NULL
OPTIONAL MATCH (dep)<-[o:OWNS]-(owner:Person)
RETURN prod.name AS product, dep.model_id AS model, r.verdict AS verdict, r.created_at AS decided_at,
       owner.name AS owner, r.id AS ruling_id;
"""

T7 = """
MATCH (r:Ruling {id: $ruling_id})-[ro:RESTS_ON]->(f:Fact)
OPTIONAL MATCH (e:Event)-[on:ON]->(r)
OPTIONAL MATCH (p:Person)-[sg:SIGNED]->(e)
RETURN r.verdict AS verdict,
       collect(DISTINCT {model_id: f.model_id, sha: f.sha, license_key: f.license_key, clause_ids: f.clause_ids}) AS facts,
       collect(DISTINCT {kind: e.kind, at: e.at, by: p.name}) AS events;
"""

T8 = """
MATCH (r:Ruling)-[:RESTS_ON]->(f:Fact)
WHERE any(c IN f.clause_ids WHERE c IN $clause_ids)
OPTIONAL MATCH (newer:Ruling)-[s:SUPERSEDES]->(r)
WITH r, f, newer, s
WHERE newer IS NULL
MATCH (r)-[fr:FOR]->(dep:Deployment)<-[o:OWNS]-(owner:Person)
RETURN DISTINCT r.id AS ruling_id, dep.id AS deployment_id, owner.id AS owner_id;
"""

A1 = """
CALL algo.pageRank('Model', 'DERIVED_FROM') YIELD node, score
WITH node, score
WHERE node.declared_differs = true
RETURN node.id AS model, score
ORDER BY score DESC
LIMIT 20;
"""

A2 = """
CALL algo.betweenness({nodeLabels: ['Model'], relationshipTypes: ['DERIVED_FROM'], samplingSize: 64})
YIELD node, score
RETURN node.id AS model, score
ORDER BY score DESC
LIMIT 20;
"""

A3 = """
CALL algo.labelPropagation({nodeLabels: ['Model'], relationshipTypes: ['DERIVED_FROM'], maxIterations: 10})
YIELD node, communityId
WITH communityId, collect(node.id) AS models
WHERE size(models) > 1
RETURN communityId, size(models) AS size, models[0..10] AS sample
ORDER BY size DESC
LIMIT 50;
"""

A4 = """
MATCH (m:Model {id: $model_id}), (r:Model {id: $root_id})
WITH shortestPath((m)-[:DERIVED_FROM*1..6]->(r)) AS p
RETURN p IS NULL AS no_path,
       CASE WHEN p IS NULL THEN [] ELSE [n IN nodes(p) | n.id] END AS path,
       CASE WHEN p IS NULL THEN 0 ELSE length(p) END AS hops;
"""

A5 = """
MATCH (m:Model {id: $model_id})
CALL algo.SSpaths({sourceNode: m, relTypes: ['DERIVED_FROM'], maxLen: 6, pathCount: 50})
YIELD path, pathWeight
RETURN [n IN nodes(path) | n.id] AS path, length(path) AS hops
LIMIT 50;
"""

O1 = """
MERGE (p:Provider {slug: $slug})
SET p.name = $name, p.hq = $hq, p.datacenters = $datacenters,
    p.tos_url = $tos_url, p.privacy_url = $privacy_url, p.updated_at = $now;
"""

O2 = """
MERGE (h:HostedModel {id: $or_id})
SET h.name = $name, h.updated_at = $now
WITH h
MERGE (m:Model {id: $hf_id})
MERGE (h)-[:IS]->(m);
"""

O3 = """
MATCH (h:HostedModel {id: $or_id})
MERGE (p:Provider {slug: $provider_slug})
MERGE (p)-[s:SERVES]->(h)
SET s.quantization = $quantization, s.tag = $tag, s.status = $status, s.uptime_30m = $uptime_30m;
"""

O4 = """
MATCH (h:HostedModel {id: $or_id})<-[s:SERVES]-(p:Provider)
WHERE any(dc IN coalesce(p.datacenters, []) WHERE dc IN $allowed_countries)
RETURN p.slug AS provider, p.name AS name, p.hq AS hq, p.datacenters AS datacenters,
       s.quantization AS quantization, s.uptime_30m AS uptime
ORDER BY uptime DESC;
"""

O5 = """
MATCH (h:HostedModel {id: $or_id})-[:IS]->(m:Model)
RETURN m.id AS hf_id;
"""

L1 = """
MERGE (t:LicenseText {id: $text_id})
ON CREATE SET t.url = $url, t.sha = $sha, t.fetched_at = $now
WITH t
UNWIND $clause_ids AS cid
MATCH (c:Clause {id: cid})
MERGE (c)-[:FROM_TEXT]->(t);
"""

L2 = """
MATCH (t:LicenseText {url: $url})
RETURN t.sha AS sha, t.fetched_at AS fetched_at
ORDER BY fetched_at DESC
LIMIT 1;
"""

C1 = """
MERGE (l:License {key: $license_key})
SET l.name = $name, l.url = $url
MERGE (c:Clause {id: $id})
SET c.kind = $kind, c.effect = $effect, c.applies_when = $applies_when, c.check = $check,
    c.summary = $summary, c.quote = $quote, c.locator = $locator, c.source_url = $source_url,
    c.source_raw_url = $source_raw_url, c.section = $section
MERGE (l)-[:IMPOSES]->(c);
"""

C2 = """
CREATE (:ClauseLoad {id: $id, at: $now, resolved: $resolved, unresolved: $unresolved});
"""

C3 = """
MATCH (m:Model {id: $model_id})
RETURN m.name_starts_with AS name_starts_with, m.card_has_llama_notice AS card_has_llama_notice,
       m.has_license_file AS has_license_file, m.declared_license AS declared_license,
       m.pipeline_tag AS pipeline_tag;
"""

C4 = """
MATCH (c:Clause)
RETURN sum(CASE WHEN c.quote = '' OR c.quote IS NULL THEN 0 ELSE 1 END) AS resolved,
       sum(CASE WHEN c.quote = '' OR c.quote IS NULL THEN 1 ELSE 0 END) AS unresolved;
"""

W0 = """
CREATE VECTOR INDEX FOR (m:Model) ON (m.dna) OPTIONS {dimension:1024, similarityFunction:'cosine'}
"""

W1 = """
MATCH (m:Model {id:$id}) SET m.dna = vecf32($dna), m.dna_sig = $sig, m.dna_status = 'OK', m.dna_at = $now RETURN m.id
"""

W1B = """
MATCH (m:Model {id:$id}) SET m.dna_status = $status, m.dna_at = $now RETURN m.id
"""

W2 = """
MATCH (c:Model {id:$id}) WHERE c.dna_status = 'OK' AND NOT coalesce(c.dna_reference, false)
CALL db.idx.vector.queryNodes('Model', 'dna', $k, c.dna) YIELD node, score
WITH c, node, 1 - score AS sim
WHERE node <> c AND node.dna_sig = c.dna_sig AND node.created_at < c.created_at AND sim >= $min_sim
RETURN node.id AS parent, sim, coalesce(node.is_root, false) AS is_root, node.created_at AS created_at
ORDER BY sim DESC, is_root DESC, created_at ASC LIMIT 5
"""

W3 = """
MATCH (c:Model {id:$child}), (p:Model {id:$parent})
MERGE (c)-[e:DERIVED_FROM]->(p)
ON CREATE SET e.relation = 'inferred', e.source = 'inferred', e.method = 'weights', e.conf = $sim, e.tier = $tier,
  e.evidence = $evidence, e.confirmations = 0, e.confirmers = []
SET e.weights_sim = $sim
RETURN e.source AS source, e.method AS method, e.tier AS tier, e.weights_sim AS weights_sim
"""

W4 = """
MATCH (c:Model)-[e:DERIVED_FROM]->(p:Model)
WHERE e.method IN ['weights', 'weights_merge'] AND NOT (c)-[:DERIVED_FROM {source:'declared'}]->()
OPTIONAL MATCH path = (p)-[:DERIVED_FROM*0..6]->(r:Model {is_root:true})
WITH c, e, p, r, path ORDER BY length(path) DESC
WITH c, e, p, collect(r)[0] AS root
RETURN c.id AS model, c.declared_license AS card_license, c.format AS format, p.id AS weights_parent,
  coalesce(e.weights_sim, e.weights_r2) AS score, e.share AS share, root.id AS root, root.declared_license AS root_license
ORDER BY score DESC LIMIT $limit
"""

W5 = """
MATCH (c:Model)-[:DERIVED_FROM {source:'declared'}]->(dp:Model), (c)-[w:DERIVED_FROM {method:'weights'}]->(wp:Model)
WHERE dp <> wp AND NOT (dp)-[:DERIVED_FROM*1..6]->(wp) AND NOT (wp)-[:DERIVED_FROM*1..6]->(dp)
RETURN c.id AS model, dp.id AS declared_parent, wp.id AS weights_parent, w.weights_sim AS sim
ORDER BY sim DESC LIMIT $limit
"""

W6 = """
MATCH (m:Model) RETURN coalesce(m.dna_status, 'NOT_RUN') AS status, count(m) AS models ORDER BY models DESC
"""

W7 = """
MATCH (c:Model {id:$child})
UNWIND $parents AS pr
MATCH (p:Model {id:pr.id})
MERGE (c)-[e:DERIVED_FROM]->(p)
ON CREATE SET e.relation = 'merge', e.source = 'inferred', e.method = 'weights_merge', e.conf = pr.r2, e.tier = $tier,
  e.share = pr.share, e.evidence = pr.evidence, e.confirmations = 0, e.confirmers = []
SET e.weights_share = pr.share, e.weights_r2 = pr.r2
RETURN p.id AS parent, e.source AS source, e.method AS method, e.share AS share, e.weights_share AS weights_share
"""

W8 = """
MATCH p = (m:Model {id:$id})-[:DERIVED_FROM*1..6]->(r:Model)
WHERE (coalesce(r.is_root, false) OR NOT (r)-[:DERIVED_FROM]->()) AND all(e IN relationships(p) WHERE e.tier >= $min_tier)
WITH r, sum(reduce(s = 1.0, e IN relationships(p) | s * coalesce(e.share, 1.0))) AS raw
RETURN r.id AS root, coalesce(r.is_root, false) AS is_root, r.declared_license AS root_license, CASE WHEN raw > 1.0 THEN 1.0 ELSE raw END AS exposure
ORDER BY exposure DESC
"""

W9 = """
MATCH (m:Model {id:$id})
SET m.format = $format, m.gguf_file = $file, m.gguf_license = $gguf_license, m.gguf_basename = $basename
WITH m WHERE $license_key IS NOT NULL
MATCH (l:License {key:$license_key})
MERGE (m)-[d:DECLARES]->(l) ON CREATE SET d.source = 'gguf_meta', d.as_of_sha = $sha
RETURN m.id, d.source
"""

W10 = """
UNWIND $ids AS rid
MATCH (m:Model {id: rid})
SET m.dna_reference = true
RETURN count(m) AS marked
"""

W11 = """
MATCH (m:Model) WHERE m.id IN $ids AND m.dna_status = 'OK'
RETURN m.id AS id, m.dna AS dna, m.dna_sig AS sig
"""

W12 = """
MATCH (m:Model) WHERE m.dna_status = 'OK' AND NOT coalesce(m.dna_reference, false)
  AND NOT (m)-[:DERIVED_FROM {method:'weights'}]->() AND NOT (m)-[:DERIVED_FROM {method:'weights_merge'}]->()
RETURN m.id AS id ORDER BY m.created_at
"""

W13 = """
MATCH (m:Model) WHERE m.id IN $ids
RETURN m.id AS id, m.sha AS sha, m.dna_status AS status
"""

X1 = """
CREATE (f:FanOut {id: $id, model_id: $model_id, reason: $reason, at: $now, descendants: $descendants,
                  not_inherited: $not_inherited, reopened: $reopened, graphs: $graphs})
RETURN f.id AS id
"""

X2 = """
MATCH (p:Person {id: $person_id})
CREATE (e:Event {id: $event_id, kind: 'CONFIRMED_EDGE', at: $now, child: $child, parent: $parent})
CREATE (e)-[:BY]->(p)
RETURN e.id AS id
"""

X3 = """
MATCH (c:Model {id: $child})-[e:DERIVED_FROM]->(p:Model {id: $parent})
RETURN e.tier AS tier, coalesce(e.confirmations, 0) AS confirmations, e.source AS source, e.relation AS relation
"""

X4 = """
MATCH (f:FanOut)
RETURN f.id AS id, f.model_id AS model_id, f.reason AS reason, f.at AS at, f.descendants AS descendants,
       f.not_inherited AS not_inherited, f.reopened AS reopened, f.graphs AS graphs
ORDER BY f.at DESC LIMIT $limit
"""

X5 = """
MATCH (m:Model {id: $mirror})-[:HAS_FP]->(f:Fingerprint {kind: 'config_fp'}), (o:Model {id: $official})
MERGE (o)-[:HAS_FP]->(f)
RETURN count(f) AS copied
"""

X6 = """
MATCH (:Model {id: $child})-[e:DERIVED_FROM]->(:Model {id: $parent})
SET e.confirmers = $confirmers, e.confirmations = size($confirmers), e.tier = $tier
RETURN e.tier AS tier, e.confirmations AS confirmations
"""

W14 = """
MATCH ()-[e:DERIVED_FROM]->()
WHERE e.source = 'inferred' AND e.method IN ['weights', 'weights_merge']
WITH collect(e) AS edges
FOREACH (x IN edges | DELETE x)
RETURN size(edges) AS removed
"""

W15 = """
MATCH (m:Model) WHERE m.id IN $ids AND coalesce(m.dna_reference, false)
RETURN m.id AS id
"""

X7 = """
MATCH (c:Model)-[e:DERIVED_FROM]->(:Model {id: $alias})
RETURN c.id AS child, properties(e) AS props
"""

X8 = """
MATCH (c:Model {id: $child}), (k:Model {id: $canonical})
MERGE (c)-[n:DERIVED_FROM]->(k)
ON CREATE SET n += $props
RETURN n.tier AS tier
"""

X9 = """
MATCH (a:Model {id: $alias}), (k:Model {id: $canonical})
SET k.aliases = CASE WHEN $alias IN coalesce(k.aliases, []) THEN k.aliases ELSE coalesce(k.aliases, []) + [$alias] END
DETACH DELETE a
RETURN k.id AS canonical
"""

X10 = """
MATCH (:Model)-[:DERIVED_FROM]->(p:Model)
RETURN DISTINCT p.id AS id
"""

X11 = """
MERGE (s:Sandbox {name: $name})
SET s.expires_at = $expires_at, s.token_hash = $token_hash, s.template = $template
RETURN s.name AS name
"""

X12 = """
MATCH (s:Sandbox)
RETURN s.name AS name, s.expires_at AS expires_at, s.token_hash AS token_hash, s.template AS template
"""

X13 = """
MATCH (s:Sandbox {name: $name})
DELETE s
RETURN 1 AS removed
"""

QUERIES = {
    "SCHEMA": SCHEMA,
    "I1": I1,
    "I2": I2,
    "I3": I3,
    "I4": I4,
    "I5": I5,
    "Q1": Q1,
    "Q2": Q2,
    "Q3": Q3,
    "R1": R1,
    "R2": R2,
    "R3": R3,
    "D1": D1,
    "D2": D2,
    "D3": D3,
    "P1": P1,
    "T1": T1,
    "T2": T2,
    "T3": T3,
    "T4": T4,
    "T5": T5,
    "T9": T9,
    "T10": T10,
    "T6": T6,
    "T7": T7,
    "T8": T8,
    "A1": A1,
    "A2": A2,
    "A3": A3,
    "A4": A4,
    "A5": A5,
    "O1": O1,
    "O2": O2,
    "O3": O3,
    "O4": O4,
    "O5": O5,
    "L1": L1,
    "L2": L2,
    "C1": C1,
    "C2": C2,
    "C3": C3,
    "C4": C4,
    "W0": W0,
    "W1": W1,
    "W1B": W1B,
    "W2": W2,
    "W3": W3,
    "W4": W4,
    "W5": W5,
    "W6": W6,
    "W7": W7,
    "W8": W8,
    "W9": W9,
    "W10": W10,
    "W11": W11,
    "W12": W12,
    "W13": W13,
    "X1": X1,
    "X2": X2,
    "X3": X3,
    "X4": X4,
    "X5": X5,
    "X6": X6,
    "W14": W14,
    "W15": W15,
    "X7": X7,
    "X8": X8,
    "X9": X9,
    "X10": X10,
    "X11": X11,
    "X12": X12,
    "X13": X13,
}
