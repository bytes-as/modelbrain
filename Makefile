# ModelBrain local targets (G018). Requires Docker; the web app also needs Node.js 22.
API ?= http://localhost:8000
WEB ?= http://localhost:3001

.PHONY: up down web test smoke eval seed reset crawl demo-reset export import

up:            ## start FalkorDB and the API
	docker compose up -d --build

down:          ## stop everything (data stays in the falkordb-data volume)
	docker compose down

web:           ## run the web app on port 3001
	cd apps/web && npm install && npm run dev -- -p 3001

test:          ## API tests against the FalkorDB service container
	docker compose run --rm --no-deps -v "$(CURDIR):/repo" -w /repo/services/api api sh -c 'pip install -q -e ".[dev]" >/dev/null && pytest -q'

smoke:         ## health, verdicts, replay, weight DNA, MCP and pages
	ADMIN_TOKEN=$$(grep '^ADMIN_TOKEN=' .env | cut -d= -f2-) scripts/smoke.sh $(API) $(WEB)

eval:          ## re-run the frozen eval and write eval/report.json
	ADMIN_TOKEN=$$(grep '^ADMIN_TOKEN=' .env | cut -d= -f2-) python3 -I eval/run_eval.py --api $(API)

seed:          ## re-create missing demo tenants (restart runs the bootstrap)
	docker compose restart api

reset:         ## delete and re-seed the fictional tenant graphs only, never the hub
	docker compose exec falkordb redis-cli GRAPH.DELETE tenant_kestrel || true
	docker compose exec falkordb redis-cli GRAPH.DELETE tenant_harbor || true
	docker compose restart api

crawl:         ## fingerprint the references and demo findings (needs ADMIN_TOKEN in .env)
	curl -s -X POST $(API)/api/admin/dna/crawl -H "Authorization: Bearer $$(grep '^ADMIN_TOKEN=' .env | cut -d= -f2-)" \
	  -H 'content-type: application/json' -d '{"include_scout_findings":true}'

demo-reset:    ## put the compounding demo back to tier 1 with one confirmation
	curl -s -X POST $(API)/api/admin/demo/compounding -H "Authorization: Bearer $$(grep '^ADMIN_TOKEN=' .env | cut -d= -f2-)"

export:        ## snapshot hub + tenant graphs to exports/ (DUMP), for seeding a deployment
	docker compose run --rm --no-deps -v "$(CURDIR):/repo" -w /repo api python scripts/graphs.py export --host falkordb --port 6379 --out exports

import:        ## restore exports/ into FALKOR_HOST:FALKOR_PORT (password from FALKORDB_PASSWORD)
	docker run --rm -v "$(CURDIR):/repo" -w /repo -e FALKORDB_PASSWORD modelbrain-api \
	  python scripts/graphs.py import --host $(FALKOR_HOST) --port $(FALKOR_PORT) --in exports --replace
