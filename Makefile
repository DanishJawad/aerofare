# The benchmark runs on the MySQL image CI tests against, read from the
# workflow so the two cannot drift apart.
BENCH_IMAGE := $(shell sed -n 's/^ *image: *\(mysql:[^ ]*\).*/\1/p' .github/workflows/ci.yml)
BENCH_PORT ?= 3317
BENCH_CONTAINER := aerofare-bench-mysql
BENCH_URL := mysql+pymysql://root:bench@127.0.0.1:$(BENCH_PORT)/aerofare_bench

.PHONY: bench
# A fresh container every time, removed on exit even if the script fails. The
# app settings are placeholders: importing app code reads them, and
# DATABASE_URL points at the benchmark server so nothing can reach the dev DB.
bench:
	@test -n "$(BENCH_IMAGE)" || { echo "No mysql image found in .github/workflows/ci.yml"; exit 1; }
	@trap 'docker rm -f $(BENCH_CONTAINER) >/dev/null 2>&1' EXIT; \
	set -e; \
	docker rm -f $(BENCH_CONTAINER) >/dev/null 2>&1 || true; \
	docker run -d --rm --name $(BENCH_CONTAINER) -e MYSQL_ROOT_PASSWORD=bench \
		-p 127.0.0.1:$(BENCH_PORT):3306 $(BENCH_IMAGE) >/dev/null; \
	echo "Waiting for $(BENCH_IMAGE) on port $(BENCH_PORT)..."; \
	for i in $$(seq 1 90); do \
		docker exec $(BENCH_CONTAINER) mysql -h127.0.0.1 -uroot -pbench -e 'SELECT 1' >/dev/null 2>&1 && break; \
		sleep 2; \
	done; \
	docker exec $(BENCH_CONTAINER) mysql -h127.0.0.1 -uroot -pbench -e 'SELECT 1' >/dev/null 2>&1 \
		|| { echo "MySQL did not start"; exit 1; }; \
	BENCH_IMAGE=$(BENCH_IMAGE) BENCH_DATABASE_URL=$(BENCH_URL) DATABASE_URL=$(BENCH_URL) \
	REDIS_URL=redis://127.0.0.1:6379/15 SECRET_KEY=bench-only-placeholder-0123456789abcdef0123456789abcdef \
	ALGORITHM=HS256 ACCESS_TOKEN_EXPIRY_MINUTES=30 \
	uv run python -m scripts.bench_route_search
