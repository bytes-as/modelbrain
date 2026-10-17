// Fictional demo tenant: Harbor Apps Inc. (fictional). Load into graph "tenant_harbor".
// Load once into an EMPTY graph (the loader runs GRAPH.DELETE first): this file uses CREATE.
CREATE (c:Company {slug:'harbor', name:'Harbor Apps Inc. (fictional)', hq_country:'US', eu:false, mau:2000000})
CREATE (t1:Team {id:'har_team_mobile', name:'Mobile'})-[:PART_OF]->(c)
CREATE (t2:Team {id:'har_team_platform', name:'Platform'})-[:PART_OF]->(c)
CREATE (p1:Person {id:'har_dana', name:'Dana Ortiz (fictional)', role:'owner'})-[:MEMBER_OF]->(t1)
CREATE (p2:Person {id:'har_sam', name:'Sam Lee (fictional)', role:'legal'})-[:MEMBER_OF]->(t1)
CREATE (p3:Person {id:'har_priya', name:'Priya Nair (fictional)', role:'engineer'})-[:MEMBER_OF]->(t2)
CREATE (pr1:Product {id:'har_photo_notes', name:'Photo Notes', commercial:true, markets:['US'], distributes_weights:false})
CREATE (pr2:Product {id:'har_ticket_triage', name:'Ticket Triage', commercial:true, markets:['US','CA'], distributes_weights:false})
CREATE (t1)-[:OWNS]->(pr1)
CREATE (t2)-[:OWNS]->(pr2)
CREATE (d1:Deployment {id:'har_dep_photo', model_id:'Xkev/Llama-3.2V-11B-cot', pinned_sha:'', env:'prod'})
CREATE (d2:Deployment {id:'har_dep_triage', model_id:'shuyuej/Llama-3.2-1B-GPTQ', pinned_sha:'', env:'prod'})
CREATE (pr1)-[:RUNS]->(d1)
CREATE (pr2)-[:RUNS]->(d2)
CREATE (p1)-[:OWNS {from:'2026-08-20', until:null}]->(d1)
CREATE (p3)-[:OWNS {from:'2026-10-01', until:null}]->(d2);
