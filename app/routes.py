"""HTTP routes for case import. This module must not use postponed annotations
so FastAPI can resolve ``Request`` at route-registration time.
"""

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse

from app.chat import answer
from app.import_service import LendingImportError, import_application
from app.ontology import schema_public, validate_graph
from app.pipeline import list_applications
from app.retrieve import retrieve

IMPORT_PAGE = Path(__file__).resolve().parent / "import_page.html"
RETRIEVE_PAGE = Path(__file__).resolve().parent / "retrieve_page.html"
CHAT_PAGE = Path(__file__).resolve().parent / "chat_page.html"
ONTOLOGY_PAGE = Path(__file__).resolve().parent / "ontology_page.html"


def _esc(text):
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _applications_html(graph):
    items = list_applications(graph)
    if not items:
        return "<p class=\"hint\">还没有案件。</p>"
    rows = []
    for item in items:
        rows.append(
            f"<li><code>{item.get('application_id') or item.get('id')}</code> — {item.get('name')}</li>"
        )
    return "<ul>" + "".join(rows) + "</ul>"


def _results_html(payload):
    if not payload.get("query"):
        return ""
    parts = ["<h2>检索结果</h2>"]
    if payload.get("chunks"):
        parts.append("<h3>证据片段</h3>")
        for hit in payload["chunks"]:
            parts.append(
                "<div class='hit'><div class='meta'>"
                f"{hit.get('kind')} · {hit.get('application_id')} · "
                f"score {hit.get('score')} · {hit.get('source')}</div>"
                f"<pre>{hit.get('text')}</pre></div>"
            )
    if payload.get("decisions"):
        parts.append("<h3>决策</h3>")
        for decision in payload["decisions"]:
            parts.append(
                "<div class='decision'><div class='meta'>"
                f"{decision.get('category')} → {decision.get('outcome')}</div>"
                f"<p>{decision.get('scenario')}</p>"
                f"<p>{decision.get('reasoning') or ''}</p></div>"
            )
    if payload.get("caused"):
        parts.append("<h3>因果链</h3><ul>")
        for link in payload["caused"]:
            parts.append(f"<li><code>{link.get('from')}</code> CAUSED <code>{link.get('to')}</code></li>")
        parts.append("</ul>")
    if payload.get("entities"):
        parts.append("<h3>相关实体</h3><ul>")
        for entity in payload["entities"]:
            parts.append(
                f"<li>{entity.get('text')} <span class='meta'>[{entity.get('type')}]</span></li>"
            )
        parts.append("</ul>")
    if len(parts) == 1:
        parts.append("<p class='hint'>没有命中。试着带上申请人名称，或问「为什么转人工」。</p>")
    return "".join(parts)


def _answer_html(payload):
    if not payload.get("query"):
        return ""
    source = payload.get("source") or "extractive"
    label = "Ollama" if source == "ollama" else "图谱摘录（未调用模型）"
    return (
        "<h2>回答</h2>"
        f"<div class='answer'><div class='meta'>{label}</div>"
        f"<p>{_esc(payload.get('answer')).replace(chr(10), '<br />')}</p></div>"
    )


def _ontology_report_html(report):
    if report.get("conforms"):
        return (
            f"<p class='ok'>当前图谱符合本体（检查了 {report.get('checked')} 个节点）。</p>"
        )
    items = "".join(
        f"<li><code>{_esc(item.get('id'))}</code> — {_esc(item.get('message'))}</li>"
        for item in report.get("violations") or []
    )
    return f"<div class='err'><p>不符合本体</p><ul>{items}</ul></div>"


def _ontology_fields_html(schema):
    rows = []
    for prop in (schema.get("ontology") or {}).get("properties") or []:
        required = "是" if prop.get("required") else "否"
        rows.append(
            "<tr>"
            f"<td>{_esc(prop.get('domain'))}</td>"
            f"<td><code>{_esc(prop.get('name'))}</code></td>"
            f"<td>{required}</td>"
            f"<td>{_esc(prop.get('description'))}</td>"
            "</tr>"
        )
    return (
        "<table><tr><th>类</th><th>属性</th><th>必填</th><th>说明</th></tr>"
        + "".join(rows)
        + "</table>"
    )


def _store(vector_store):
    if isinstance(vector_store, dict):
        return vector_store.get("store")
    return vector_store


def attach_lending_routes(app, session, vector_store=None):
    async def import_page():
        html = IMPORT_PAGE.read_text(encoding="utf-8")
        html = html.replace("{{applications}}", _applications_html(session.graph))
        return HTMLResponse(html)

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
            result = import_application(
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
            html = (
                f"<html><body><p class='err'>{exc}</p>"
                "<p><a href='/lending'>返回</a></p></body></html>"
            )
            return HTMLResponse(html, status_code=400)
        html = (
            "<html><body><p class='ok'>已导入 "
            f"<strong>{result['applicant_name']}</strong> "
            f"(<code>{result['application_id']}</code>)，"
            f"{result['entity_count']} 个实体，"
            f"{len(result['decisions'])} 条决策。</p>"
            "<p><a href='/'>打开知识图谱</a> · "
            "<a href='/lending/retrieve'>图谱检索</a> · "
            "<a href='/lending'>继续导入</a></p>"
            "</body></html>"
        )
        return HTMLResponse(html)

    async def retrieve_page(request: Request):
        query = ""
        payload = {}
        if request.method == "POST":
            form = await request.form()
            query = str(form.get("query") or "")
            payload = retrieve(session.graph, query, store=_store(vector_store))
        html = RETRIEVE_PAGE.read_text(encoding="utf-8")
        html = html.replace("{{query}}", query.replace("&", "&amp;").replace('"', "&quot;"))
        html = html.replace("{{results}}", _results_html(payload))
        return HTMLResponse(html)

    async def retrieve_api(request: Request):
        body = await request.json()
        query = str(body.get("query") or "")
        return retrieve(session.graph, query, store=_store(vector_store))

    async def chat_page(request: Request):
        query = ""
        payload = {}
        if request.method == "POST":
            form = await request.form()
            query = str(form.get("query") or "")
            payload = answer(session.graph, query, store=_store(vector_store))
        html = CHAT_PAGE.read_text(encoding="utf-8")
        html = html.replace("{{query}}", _esc(query))
        html = html.replace("{{answer}}", _answer_html(payload))
        html = html.replace("{{results}}", _results_html(payload))
        return HTMLResponse(html)

    async def chat_api(request: Request):
        body = await request.json()
        query = str(body.get("query") or "")
        return answer(session.graph, query, store=_store(vector_store))

    async def ontology_page():
        schema = schema_public()
        report = validate_graph(session.graph)
        html = ONTOLOGY_PAGE.read_text(encoding="utf-8")
        html = html.replace("{{report}}", _ontology_report_html(report))
        html = html.replace("{{fields}}", _ontology_fields_html(schema))
        html = html.replace("{{shacl}}", _esc(schema.get("shacl")))
        return HTMLResponse(html)

    async def ontology_api():
        return {**schema_public(), "validation": validate_graph(session.graph)}

    async def validate_api():
        return validate_graph(session.graph)

    app.add_api_route("/lending", import_page, methods=["GET"])
    app.add_api_route("/lending/retrieve", retrieve_page, methods=["GET", "POST"])
    app.add_api_route("/lending/chat", chat_page, methods=["GET", "POST"])
    app.add_api_route("/lending/ontology", ontology_page, methods=["GET"])
    app.add_api_route("/api/lending/applications", list_apps, methods=["GET"])
    app.add_api_route("/api/lending/import", import_app, methods=["POST"])
    app.add_api_route("/api/lending/retrieve", retrieve_api, methods=["POST"])
    app.add_api_route("/api/lending/chat", chat_api, methods=["POST"])
    app.add_api_route("/api/lending/ontology", ontology_api, methods=["GET"])
    app.add_api_route("/api/lending/validate", validate_api, methods=["POST"])
    app.router.routes[0:0] = app.router.routes[-10:]
    del app.router.routes[-10:]
