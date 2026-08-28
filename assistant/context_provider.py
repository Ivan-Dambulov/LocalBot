from files.extractors import extract_text
from web.search import format_search_context


MAX_CONTEXT_CHARS = 80000


class ContextProvider:
    def build_context(
        self,
        query,
        search_results,
        attachments,
    ):
        parts = []

        if search_results:
            parts.append(
                format_search_context(
                    query,
                    search_results,
                )
            )

        if attachments:
            document_parts = []

            for file_path in attachments:
                try:
                    text = extract_text(file_path)

                    document_parts.append(
                        f"""
FILE: {file_path.name}

{text}
"""
                    )

                except Exception as exc:
                    document_parts.append(
                        f"""
FILE: {file_path.name}

ERROR:
{exc}
"""
                    )

            parts.append(
                "\n\n".join(document_parts)
            )

        context = "\n\n".join(parts)

        return context[:MAX_CONTEXT_CHARS]