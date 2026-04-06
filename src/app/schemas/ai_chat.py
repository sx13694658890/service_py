from typing import Literal

from pydantic import BaseModel, Field


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., max_length=16_000)


class ChatRequest(BaseModel):
    messages: list[ChatMessageIn] = Field(..., min_length=1, max_length=100)
    conversation_id: str | None = Field(default=None, max_length=128)
    quick_question_id: str | None = Field(default=None, max_length=128)


class SourceOut(BaseModel):
    title: str
    path: str


class AssistantMessageOut(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class ChatResponse(BaseModel):
    message: AssistantMessageOut
    sources: list[SourceOut]
    route: Literal["answer", "human_handoff"] | None = None


class QuickQuestionItemOut(BaseModel):
    id: str
    label: str


class QuickQuestionsResponse(BaseModel):
    items: list[QuickQuestionItemOut]
