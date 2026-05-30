import logging
from openai import AsyncOpenAI

from core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_API_BASE)
    return _client

SUMMARY_PROMPT = """Progressively summarize the lines of conversation provided, adding onto the previous summary returning a new summary.

Current summary:
{summary}

New lines of conversation:
{new_lines}

New summary (in Chinese):"""


class ConversationMemory:
    """Lightweight conversation summary memory using LLM for summarization."""

    def __init__(self, summary: str = ""):
        self.summary = summary

    async def update_summary(self, user_input: str, assistant_response: str) -> str:
        """Compress conversation turn into updated summary."""
        if not self.summary:
            self.summary = f"User asked: {user_input}. Assistant replied: {assistant_response}"
            return self.summary

        try:
            client = _get_client()
            response = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                temperature=0.1,
                max_tokens=512,
                messages=[
                    {"role": "user", "content": SUMMARY_PROMPT.format(
                        summary=self.summary,
                        new_lines=f"User: {user_input}\nAssistant: {assistant_response}",
                    )}
                ],
            )
            self.summary = response.choices[0].message.content or self.summary
        except Exception as e:
            logger.warning(f"LLM summarization failed, using fallback: {e}")
            self.summary = f"{self.summary}\nUser: {user_input}\nAssistant: {assistant_response}"
        return self.summary

    async def update_summary_batch(self, pairs: list[tuple[str, str]]) -> str:
        """Compress multiple conversation turns into a single summary via one LLM call."""
        if not pairs:
            return self.summary

        new_lines = "\n".join(
            f"User: {user}\nAssistant: {assistant}" for user, assistant in pairs
        )

        if not self.summary:
            lines = "\n".join(
                f"User asked: {user}. Assistant replied: {assistant}" for user, assistant in pairs
            )
            self.summary = lines
            return self.summary

        try:
            client = _get_client()
            response = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                temperature=0.1,
                max_tokens=512,
                messages=[
                    {"role": "user", "content": SUMMARY_PROMPT.format(
                        summary=self.summary,
                        new_lines=new_lines,
                    )}
                ],
            )
            self.summary = response.choices[0].message.content or self.summary
        except Exception as e:
            logger.warning(f"LLM summarization failed, using fallback: {e}")
            self.summary = f"{self.summary}\n{new_lines}"
        return self.summary

    def get_summary(self) -> str:
        return self.summary
