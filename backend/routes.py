"""Lending JSON HTTP API.

This module must not use postponed annotations so FastAPI can resolve
``Request`` at route-registration time. It does not compose HTML.
"""

import asyncio
import os

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.chat import answer
from backend.import_service import LendingImportError, import_application
from backend.ontology import schema_public, validate_graph
from backend.pipeline import list_applications
from backend.retrieve import retrieve

_DEFAULT_CORS = (
    "http://localhost:8080,http://127.0.0.1:8080,"
    "http://localhost:8000,http://127.0.0.1:8000,"
    "http://localhost:5173,http://127.0.0.1:5173"
)


def lending_cors_origins():
    raw = os.environ.get("LENDING_CORS_ORIGINS") or _DEFAULT_CORS
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def configure_lending_cors(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=lending_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )


def _store(vector_store):
    if isinstance(vector_store, dict):
        return vector_store.get("store")
    return vector_store


def attach_lending_routes(app, session, vector_store=None):
    configure_lending_cors(app)
    async def list_apps():
        return {"applications": list_applications(session.graph)}

    async def import_app(request: Request):
        form = await request.form()
        applicant_name = str(form.get("applicant_name") or "")
        application_id = str(form.get("application_id") or "")
        high_risk = bool(form.get("high_risk"))
        thin_credit = bool(form.get("thin_credit"))
        uploads = []
        for upload in form.getlist("files"):
            filename = getattr(upload, "filename", None)
            if not filename or not hasattr(upload, "read"):
                continue
            uploads.append({"filename": filename, "content": await upload.read()})
        try:
            return import_application(
                session.graph,
                files=uploads,
                applicant_name=applicant_name,
                application_id=application_id,
                high_risk=high_risk,
                thin_credit=thin_credit,
                session=session,
                vector_store=_store(vector_store),
            )
        except LendingImportError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    async def retrieve_api(request: Request):
        body = await request.json()
        query = str(body.get("query") or "")
        return retrieve(session.graph, query, store=_store(vector_store))

    async def chat_api(request: Request):
        body = await request.json()
        query = str(body.get("query") or "")
        return await asyncio.to_thread(answer, session.graph, query, _store(vector_store))

    async def ontology_api():
        return {**schema_public(), "validation": validate_graph(session.graph)}

    async def validate_api():
        return validate_graph(session.graph)

    app.add_api_route("/api/lending/applications", list_apps, methods=["GET"])
    app.add_api_route("/api/lending/import", import_app, methods=["POST"])
    app.add_api_route("/api/lending/retrieve", retrieve_api, methods=["POST"])
    app.add_api_route("/api/lending/chat", chat_api, methods=["POST"])
    app.add_api_route("/api/lending/ontology", ontology_api, methods=["GET"])
    app.add_api_route("/api/lending/validate", validate_api, methods=["POST"])
