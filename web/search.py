from dataclasses import dataclass
from typing import List

from ddgs import DDGS


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class WebSearchError(Exception):
    """Raised when an Internet search cannot be completed."""


class WebSearcher:
    """Small wrapper around DuckDuckGo search."""

    def __init__(self, max_results: int = 5):
        self.max_results = max(1, min(max_results, 10))

    def search(self, query: str) -> List[SearchResult]:
        query = query.strip()

        if not query:
            return []

        try:
            results = DDGS().text(
                query,
                max_results=self.max_results,
            )
        except Exception as exc:
            raise WebSearchError(
                f"Internet search failed: {exc}"
            ) from exc

        output = []

        for result in results or []:
            title = str(result.get("title") or "").strip()
            url = str(result.get("href") or "").strip()
            snippet = str(result.get("body") or "").strip()

            if not url:
                continue

            output.append(
                SearchResult(
                    title=title or url,
                    url=url,
                    snippet=snippet,
                )
            )

        return output


def format_search_context(
    query: str,
    results: List[SearchResult],
) -> str:
    """Convert search results into compact LLM context."""

    if not results:
        return (
            f'No useful web results were found for "{query}".'
        )

    lines = [
        "The following information was retrieved from an Internet "
        "search.",
        "",
        f"Search query: {query}",
        "",
    ]

    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"[{index}] {result.title}",
                f"URL: {result.url}",
                f"Snippet: {result.snippet}",
                "",
            ]
        )

    lines.extend(
        [
            "Use these sources when answering the user's question.",
            "Do not invent facts that are not supported by the "
            "available sources.",
            "When using web information, cite the source using "
            "[1], [2], etc.",
        ]
    )

    return "\n".join(lines)