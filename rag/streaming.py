"""SSE event formatting and streaming generator for the RAG pipeline."""

import json
import logging
from typing import AsyncGenerator

from langchain_core.documents import Document as LCDocument
from openai import AsyncOpenAI

from core.config import settings
from rag.qa_chain import SYSTEM_PROMPT, _format_context

logger = logging.getLogger(__name__)


def format_sse_event(event_type: str, data: dict) -> str:
    """Format an SSE event as a ``data:`` line with a JSON payload.

    Args:
        event_type: The event type identifier (e.g. ``"token"``, ``"done"``).
        data: A dict that will be serialised as the event payload.

    Returns:
        A complete SSE event string ending with ``\\n\\n``.
    """
    payload = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def generate_stream(
    question: str,
    context_docs: list[tuple[LCDocument, float]],
    memory_summary: str = "",
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted events while streaming from the LLM.

    Parameters
    ----------
    question:
        The user's question.
    context_docs:
        A list of ``(Document, score)`` tuples returned by the retriever /
        reranker pipeline.
    memory_summary:
        A compressed summary of the conversation history (optional).

    Yields
    ------
    SSE ``token`` events for each content delta the LLM sends.
    A ``done`` event carrying the full raw answer once the stream finishes.
    An ``error`` event if anything goes wrong.
    """
    if not settings.DEEPSEEK_API_KEY:
        yield format_sse_event("error", {"message": "DEEPSEEK_API_KEY is not configured"})
        return

    context = _format_context(context_docs)
    prompt = SYSTEM_PROMPT.format(
        context=context,
        memory_summary=memory_summary or "No previous conversation.",
    )

    client = AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_API_BASE)
    full_answer = ""

    try:
        stream = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.STREAMING_MAX_TOKENS,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ],
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                full_answer += delta.content
                yield format_sse_event("token", {"token": delta.content})

        yield format_sse_event("done", {"answer": full_answer})

    except Exception as e:
        logger.error(f"Stream generation failed: {e}", exc_info=True)
        yield format_sse_event("error", {"message": f"LLM streaming error: {str(e)}"})
