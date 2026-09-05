#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

mkdir -p exports

"${ROOT}/scripts/download-model.sh"

echo "Building Neo4j + admin UI (Knowledge Explorer)..."
echo "  Admin UI:      http://localhost:8000"
echo "  Case import:   http://localhost:8000/lending"
echo "  Retrieve:      http://localhost:8000/lending/retrieve"
echo "  Chat:          http://localhost:8000/lending/chat"
echo "  Ontology:      http://localhost:8000/lending/ontology"
echo "  Neo4j Browser: http://localhost:7474  (neo4j / lending-demo)"
echo "  CLI demo only: docker compose --profile cli up --build --abort-on-container-exit demo"
docker compose up --build admin
