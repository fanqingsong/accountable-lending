"""Q&A generation over retrieve results. The LLM never extracts, reasons, or decides."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional

from app.retrieve import retrieve

SYSTEM_PROMPT = (
    "你是贷款审计助手。只能根据提供的图谱证据回答，禁止编造数字、政策编号或结论。"
    "证据不足就明确说不知道。用中文简短回答，点名决策链和材料出处。"
)

CompleteFn = Callable[[str, str], str]


def format_context(payload: Dict[str, Any]) -> str:
    lines = []
    for decision in payload.get("decisions") or []:
        lines.append(
            "DECISION "
            f"{decision.get('category')} -> {decision.get('outcome')}: "
            f"{decision.get('reasoning') or decision.get('scenario') or ''}"
        )
    for link in payload.get("caused") or []:
        lines.append(f"CAUSED {link.get('from')} -> {link.get('to')}")
    for hit in payload.get("chunks") or []:
        lines.append(f"CHUNK [{hit.get('kind')}] {hit.get('text')}")
    for entity in payload.get("entities") or []:
        lines.append(f"ENTITY {entity.get('text')} ({entity.get('type')})")
    return "\n".join(lines).strip()


def extractive_answer(payload: Dict[str, Any]) -> str:
    decisions = list(payload.get("decisions") or [])
    if not decisions and not (payload.get("chunks") or []):
        return "图谱里没有找到相关证据。"
    order = {"risk_classification": 0, "policy_check": 1, "final_decision": 2}
    decisions.sort(key=lambda item: order.get(str(item.get("category") or ""), 9))
    parts = []
    if decisions:
        chain = " → ".join(
            f"{item.get('category')}={item.get('outcome')}" for item in decisions
        )
        parts.append(f"根据图谱，决策链为：{chain}。")
        for item in decisions:
            if item.get("reasoning"):
                parts.append(str(item["reasoning"]))
    entities = [str(item.get("text")) for item in payload.get("entities") or [] if item.get("text")]
    if entities:
        parts.append("相关实体：" + "、".join(entities[:6]) + "。")
    if not parts:
        parts.append("图谱命中了材料，但没有对应决策。请看下方证据。")
    return "\n".join(parts)


def user_prompt(query: str, context: str) -> str:
    return f"问题：{query}\n\n证据：\n{context or '（无）'}"


def ollama_complete(prompt: str, system: str) -> str:
    url = os.environ.get("OLLAMA_URL", "").strip()
    if not url:
        raise RuntimeError("OLLAMA_URL is not set")
    urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=2).read()
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
    body = json.dumps(
        {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url.rstrip("/") + "/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.loads(response.read().decode("utf-8"))
    message = data.get("message") or {}
    return str(message.get("content") or data.get("response") or "").strip()


def generate_answer(query: str, payload: Dict[str, Any], complete: Optional[CompleteFn] = None) -> Dict[str, str]:
    context = format_context(payload)
    text = extractive_answer(payload)
    source = "extractive"
    if complete is not None and context:
        generated = complete(user_prompt(query, context), SYSTEM_PROMPT)
        if generated:
            text = generated
            source = "ollama"
    return {"answer": text, "source": source, "context": context}


def answer(graph, query: str, store=None, complete: Optional[CompleteFn] = None) -> Dict[str, Any]:
    """Retrieve first, then generate. Generation never writes the graph."""
    query = (query or "").strip()
    payload = retrieve(graph, query, store=store)
    if complete is None and os.environ.get("OLLAMA_URL", "").strip():
        complete = ollama_complete
    try:
        generated = generate_answer(query, payload, complete=complete)
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError, ValueError):
        generated = generate_answer(query, payload, complete=None)
    return {**payload, **generated}
