"""actions/web_search.py — Web search via Gemini grounded + DuckDuckGo fallback

Modos:
  search   → busca geral (padrão)
  news     → notícias recentes
  research → resposta aprofundada
  price    → preço de produto
  compare  → comparação entre itens (requer parâmetro 'items')

Parâmetros aceitos pelo Gemini (no TOOLS do main.py) — adicione os novos:
  query  (str)       — termo de busca
  mode   (str)       — search | news | research | price | compare
  items  (list[str]) — itens a comparar (modo compare)
  aspect (str)       — aspecto de comparação (padrão: geral)
"""
from __future__ import annotations
import os
from typing import Any


# ── Backends ───────────────────────────────────────────────────────────────────

def _gemini_search(query: str) -> str:
    from google import genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=query,
        config={"tools": [{"google_search": {}}]},
    )
    text = "".join(
        p.text for p in response.candidates[0].content.parts
        if hasattr(p, "text") and p.text
    ).strip()
    if not text:
        raise ValueError("Gemini retornou resposta vazia.")
    return text


def _ddg_search(query: str, max_results: int = 6) -> list[dict]:
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        return [
            {"title": r.get("title", ""), "snippet": r.get("body", ""), "url": r.get("href", "")}
            for r in ddgs.text(query, max_results=max_results)
        ]


def _fmt_ddg(query: str, results: list[dict]) -> str:
    if not results:
        return f"Nenhum resultado encontrado para: {query}"
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n   {r['snippet'][:200]}\n   {r['url']}")
    return "\n\n".join(lines)


# ── Modos ──────────────────────────────────────────────────────────────────────

def _search(query: str) -> str:
    try:
        return _gemini_search(query)
    except Exception as e:
        print(f"[WebSearch] ⚠️ Gemini falhou ({e}) — usando DDG...")
        return _fmt_ddg(query, _ddg_search(query))


def _news(query: str) -> str:
    q = f"últimas notícias hoje: {query}" if query else "principais notícias do dia"
    try:
        return _gemini_search(q)
    except Exception as e:
        print(f"[WebSearch] ⚠️ Gemini news falhou ({e}) — usando DDG...")
        return _fmt_ddg(q, _ddg_search(q, max_results=8))


def _research(query: str) -> str:
    q = (
        f"Explicação completa e detalhada sobre: {query}. "
        "Inclua contexto, fatos principais, estado atual e nuances importantes."
    )
    try:
        return _gemini_search(q)
    except Exception as e:
        print(f"[WebSearch] ⚠️ Gemini research falhou ({e}) — usando DDG...")
        return _fmt_ddg(query, _ddg_search(query, max_results=10))


def _price(query: str) -> str:
    q = f"preço atual de {query} — quanto custa hoje"
    try:
        return _gemini_search(q)
    except Exception as e:
        print(f"[WebSearch] ⚠️ Gemini price falhou ({e}) — usando DDG...")
        return _fmt_ddg(query, _ddg_search(f"{query} preço comprar", max_results=6))


def _compare(items: list[str], aspect: str) -> str:
    q = f"Compare {', '.join(items)} em termos de {aspect}. Dê fatos e dados específicos."
    try:
        return _gemini_search(q)
    except Exception as e:
        print(f"[WebSearch] ⚠️ Gemini compare falhou ({e}) — usando DDG...")
    lines = [f"Comparação — {aspect.upper()}", "─" * 40]
    for item in items:
        lines.append(f"\n▸ {item}")
        for r in _ddg_search(f"{item} {aspect}", max_results=3)[:2]:
            if r.get("snippet"): lines.append(f"  • {r['snippet'][:150]}")
            if r.get("url"):     lines.append(f"    {r['url']}")
    return "\n".join(lines)


# ── Ponto de entrada — mesma assinatura do seu main.py ────────────────────────

def web_search(parameters: dict | None = None, **_: Any) -> str:
    params = parameters or {}
    query  = params.get("query", "").strip()
    mode   = params.get("mode", "search").lower().strip()
    items  = params.get("items", [])
    aspect = params.get("aspect", "geral").strip() or "geral"

    if not query and not items:
        return "Preciso de uma query para pesquisar, senhor."

    if items:
        mode = "compare"

    print(f"[WebSearch] 🔍 mode={mode!r}  query={query!r}")

    try:
        if mode == "compare":  return _compare(items or [query], aspect)
        if mode == "news":     return _news(query)
        if mode == "research": return _research(query)
        if mode == "price":    return _price(query)
        return _search(query)
    except Exception as e:
        print(f"[WebSearch] ❌ Falha total: {e}")
        return f"Erro na busca: {e}"