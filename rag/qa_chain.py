import logging
import re
from typing import List, Tuple

from langchain_core.documents import Document as LCDocument
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an enterprise knowledge base assistant. Your task is to answer questions based on the provided context fragments.

Rules:
1. Answer based ONLY on the provided context. If context lacks information, say "I cannot find relevant information in the knowledge base."
2. Always cite sources using 【来源: filename】 at the end of each sentence or paragraph that uses information from a source.
3. If multiple sources support a claim, cite all of them: 【来源: file1.md】【来源: file2.pdf】
4. Be concise and accurate. Use Chinese unless the question is in English.
5. Do not make up information or speculate beyond the context.

Context fragments:
{context}

Conversation history summary:
{memory_summary}"""


def _format_context(docs: List[Tuple[LCDocument, float]]) -> str:
    lines = []
    for i, (doc, score) in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        lines.append(f"[{i}] (Score: {score:.4f}) 【来源: {source}】\n{doc.page_content}\n")
    return "\n".join(lines)


def _parse_sources(answer: str) -> Tuple[str, list]:
    """Extract source filenames from answer and return (clean_answer, sources_list)."""
    pattern = r"【来源:\s*([^】]+)】"
    matches = re.findall(pattern, answer)
    sources = list(set(s.strip() for s in matches))
    clean = re.sub(pattern, "", answer).strip()
    return clean, sources


def extract_suggested_questions(answer: str) -> tuple[str, list[str]]:
    """Extract lines prefixed with ``Q:`` from the answer.

    Returns:
        A ``(clean_answer, questions)`` tuple where *questions* is a list of
        follow-up question strings and *clean_answer* has the ``Q:`` lines
        removed.
    """
    lines = answer.split("\n")
    clean_lines: list[str] = []
    questions: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Q:"):
            questions.append(stripped[2:].strip())
        else:
            clean_lines.append(line)
    clean = "\n".join(clean_lines).strip()
    return clean, questions


FOLLOWUP_PROMPT = """Based on the following Q&A, suggest 3 short follow-up questions the user might want to ask. Output each question on its own line starting with "Q:".

Question: {question}
Answer: {answer}

Q:"""


async def generate_followup_questions(question: str, answer: str) -> list[str]:
    """Generate suggested follow-up questions via a lightweight LLM call.

    Uses a second, cheap LLM invocation (with ``FOLLOWUP_MAX_TOKENS``) so that
    the main answer stream is not delayed.
    """
    if not settings.DEEPSEEK_API_KEY:
        return []

    try:
        client = AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_API_BASE)
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            temperature=0.3,
            max_tokens=settings.FOLLOWUP_MAX_TOKENS,
            messages=[
                {"role": "user", "content": FOLLOWUP_PROMPT.format(question=question, answer=answer)},
            ],
        )
        content = response.choices[0].message.content or ""
        # The prompt asks the LLM to prefix each line with "Q:", so we parse
        # with a synthetic prefix to make the extraction reliable.
        _, questions = extract_suggested_questions(f"Q: {content}")
        return questions
    except Exception as e:
        logger.warning(f"Failed to generate follow-up questions: {e}")
        return []


async def ask_question(
    question: str,
    context_docs: List[Tuple[LCDocument, float]],
    memory_summary: str = "",
) -> Tuple[str, list]:
    """Call DeepSeek API with context and return (answer, source_filenames)."""
    if not settings.DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY is not configured")

    context = _format_context(context_docs)
    prompt = SYSTEM_PROMPT.format(context=context, memory_summary=memory_summary or "No previous conversation.")

    answer = await _call_llm(prompt, question)
    answer, sources = _parse_sources(answer)
    return answer, sources


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
)
async def _call_llm(system_prompt: str, question: str) -> str:
    client = AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_API_BASE)
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
    )
    return response.choices[0].message.content or ""
