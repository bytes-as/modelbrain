// Fictional demo tenant: Kestrel Analytics GmbH (fictional). Load into graph "tenant_kestrel".
// Load once into an EMPTY graph (the loader runs GRAPH.DELETE first): this file uses CREATE.
// All companies and people here are fictional. Model ids are real public Hugging Face repos.
CREATE (c:Company {slug:'kestrel', name:'Kestrel Analytics GmbH (fictional)', hq_country:'DE', eu:true, mau:120000})
CREATE (t1:Team {id:'kes_team_claims', name:'Claims AI'})-[:PART_OF]->(c)
CREATE (t2:Team {id:'kes_team_support', name:'Support'})-[:PART_OF]->(c)
CREATE (p1:Person {id:'kes_lena', name:'Lena Vogt (fictional)', role:'owner'})-[:MEMBER_OF]->(t1)
CREATE (p2:Person {id:'kes_jonas', name:'Jonas Brandt (fictional)', role:'legal'})-[:MEMBER_OF]->(t1)
CREATE (p3:Person {id:'kes_mira', name:'Mira Haas (fictional)', role:'engineer'})-[:MEMBER_OF]->(t2)
CREATE (pr1:Product {id:'kes_claims_vision', name:'Claims Vision Assistant', commercial:true, markets:['DE','FR','NL'], distributes_weights:false})
CREATE (pr2:Product {id:'kes_support_copilot', name:'Support Copilot', commercial:true, markets:['DE'], distributes_weights:false})
CREATE (t1)-[:OWNS]->(pr1)
CREATE (t2)-[:OWNS]->(pr2)
CREATE (d1:Deployment {id:'kes_dep_claims', model_id:'OPEA/Llama-3.2V-11B-cot-int4-sym-inc', pinned_sha:'', env:'prod'})
CREATE (d2:Deployment {id:'kes_dep_support', model_id:'SicariusSicariiStuff/Llama-3.2-1B_Base_FP8', pinned_sha:'', env:'staging'})
CREATE (pr1)-[:RUNS]->(d1)
CREATE (pr2)-[:RUNS]->(d2)
CREATE (p1)-[:OWNS {from:'2026-09-01', until:null}]->(d1)
CREATE (p3)-[:OWNS {from:'2026-09-15', until:null}]->(d2);
// Seed rulings are written by the API on first start (Auditor), so they rest on real hub facts.
