"""Repo-relative paths shared by Application, retrieve, and adapters."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
EXPORTS_DIR = ROOT / "exports"
GRAPH_JSON = EXPORTS_DIR / "lending_graph.json"
UPLOADS = EXPORTS_DIR / "uploads"
ONTOLOGY_DIR = ROOT / "ontology"
ONTOLOGY_JSON = ONTOLOGY_DIR / "lending.json"
OWL_TTL = ONTOLOGY_DIR / "lending.ttl"
SHACL_TTL = ONTOLOGY_DIR / "lending.shacl.ttl"
ALLOWED_SUFFIXES = {".txt", ".pdf", ".docx", ".md"}
