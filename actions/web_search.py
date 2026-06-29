"""actions/web_search.py — Web search via DuckDuckGo (sem API key)"""
from __future__ import annotations
from typing import Any

def web_search(parameters: dict | None = None, **_: Any) -> str:
    params = parameters or {}
    query  = params.get("query", "").strip()
    count  = int(params.get("count", 5))

    if not query:
        return "Preciso de uma query para pesquisar, senhor."

    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=count))
        if not results:
            return "Nenhum resultado encontrado."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title','')}\n   {r.get('body','')[:200]}\n   {r.get('href','')}")
        return "\n\n".join(lines)
    except ImportError:
        return "duckduckgo-search não instalado. Execute: pip install duckduckgo-search"
    except Exception as e:
        return f"Erro na busca: {e}"
