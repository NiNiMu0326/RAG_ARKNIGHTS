"""
LangChain-compatible ChatModel wrappers for DeepSeek and SiliconFlow.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Any, Dict, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field
from backend import config
from backend.api.deepseek import DeepSeekClient
from backend.api.siliconflow import SiliconFlowClient


def _convert_messages(messages: List[BaseMessage]) -> List[Dict[str, str]]:
    """Convert LangChain messages to API dict format."""
    result = []
    for m in messages:
        if isinstance(m, SystemMessage):
            result.append({"role": "system", "content": m.content})
        elif isinstance(m, HumanMessage):
            result.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            result.append({"role": "assistant", "content": m.content})
        else:
            result.append({"role": "user", "content": str(m.content)})
    return result


class DeepSeekChatModel(BaseChatModel):
    """DeepSeek API chat model for answer generation."""

    api_key: str = Field(default="")
    model: str = Field(default="deepseek-chat")
    temperature: float = Field(default=0.7)

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

    def __init__(self, api_key: str = None, model: str = None, temperature: float = 0.7, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or config.DEEPSEEK_API_KEY
        if model:
            self.model = model
        self.temperature = temperature
        self._client = DeepSeekClient(api_key=self.api_key)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager=None,
        **kwargs: Any,
    ) -> ChatResult:
        api_messages = _convert_messages(messages)
        # 不传递 extra_body，避免 API 调用失败
        response_text = self._client.chat(
            api_messages,
            model=self.model,
            temperature=self.temperature
        )
        message = AIMessage(content=response_text)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        return "deepseek"


class SiliconFlowChatModel(BaseChatModel):
    """SiliconFlow API chat model (e.g. Qwen2.5-7B-Instruct)."""

    api_key: str = Field(default="")
    model: str = Field(default="Pro/Qwen/Qwen2.5-7B-Instruct")
    temperature: float = Field(default=0.7)

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

    def __init__(self, api_key: str = None, model: str = None, temperature: float = 0.7, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or config.SILICONFLOW_API_KEY
        if model:
            self.model = model
        self.temperature = temperature
        self._client = SiliconFlowClient(api_key=self.api_key)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager=None,
        **kwargs: Any,
    ) -> ChatResult:
        api_messages = _convert_messages(messages)
        response_text = self._client.chat(
            api_messages,
            model=self.model,
            temperature=self.temperature
        )
        message = AIMessage(content=response_text)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        return "siliconflow"
