.PHONY: test go-test upstream-test python-test frontend lint build check audit dependency-audit

go-test:
	tools/go test -race ./...
upstream-test:
	tools/upstream-test
python-test:
	tools/test -q
frontend:
	tools/frontend --test
lint:
	tools/go vet ./...
	@test -z "$$(gofmt -l cmd internal)"
	ruff check hermes_apron tests tools/*.py __init__.py
	ruff format --check hermes_apron tests tools/*.py __init__.py
build:
	tools/build
audit:
	python3 tools/audit.py
dependency-audit:
	tools/go run golang.org/x/vuln/cmd/govulncheck@v1.9.0 ./...
	python3 tools/dependency_audit.py
test: go-test python-test
check: test upstream-test lint build audit dependency-audit
