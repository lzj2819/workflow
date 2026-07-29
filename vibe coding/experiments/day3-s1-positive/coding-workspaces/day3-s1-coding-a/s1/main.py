"""Minimal in-memory notes API."""

from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, status
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator


app = FastAPI()


class CreateNote(BaseModel):
    """The sole accepted request field for creating a note."""

    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, StringConstraints(strict=True)]

    @field_validator("text")
    @classmethod
    def trim_and_validate_text(cls, value: str) -> str:
        text = value.strip()
        if not 1 <= len(text) <= 140:
            raise ValueError("text must be between 1 and 140 characters after trimming")
        return text


class NoteResponse(BaseModel):
    id: str
    text: str


notes: list[NoteResponse] = []


@app.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(note: CreateNote) -> NoteResponse:
    created_note = NoteResponse(id=str(uuid4()), text=note.text)
    notes.append(created_note)
    return created_note
