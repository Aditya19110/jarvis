"""
skills/web_search.py — DuckDuckGo search skill (no API key needed)
"""
from __future__ import annotations


def search_web(query: str, max_results: int = 4) -> list[dict]:
    """
    Search DuckDuckGo and return top results.
    Returns list of {"title": ..., "href": ..., "body": ...}
    """
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "href": r.get("href", ""),
                    "body": r.get("body", "")[:300],  # Trim to 300 chars
                })
        return results
    except Exception as e:
        return [{"title": "Search error", "href": "", "body": str(e)}]


def format_search_results(results: list[dict]) -> str:
    """Format results into a readable string."""
    if not results:
        return "No results found."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r['title']}**\n   {r['body']}\n   {r['href']}")
    return "\n\n".join(lines)
