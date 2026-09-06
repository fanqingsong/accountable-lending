#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p exports

"${ROOT}/scripts/download-model.sh"

OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:1.5b}"
echo "Starting Ollama and pulling ${OLLAMA_MODEL}..."
docker compose up -d ollama
ready=0
for _ in $(seq 1 60); do
    if curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then
        ready=1
        break
    fi
    sleep 1
done
if [[ "${ready}" -ne 1 ]]; then
    echo "Ollama did not become ready on http://127.0.0.1:11434" >&2
    exit 1
fi
docker compose exec -T ollama ollama pull "${OLLAMA_MODEL}"

echo "Building Neo4j + Qdrant + Ollama + lending-api + lending-ui + Explorer..."
echo "  Explorer:      http://localhost:8000"
echo "  lending-api:   http://localhost:8001/api/lending/applications"
echo "  Case import:   http://localhost:8080/lending"
echo "  Retrieve:      http://localhost:8080/lending/retrieve"
echo "  Chat:          http://localhost:8080/lending/chat"
echo "  Ontology:      http://localhost:8080/lending/ontology"
echo "  Neo4j Browser: http://localhost:7474  (neo4j / lending-demo)"
echo "  CLI demo only: docker compose --profile cli up --build --abort-on-container-exit demo"
docker compose up --build explorer lending-api lending-ui ollama
