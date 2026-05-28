from __future__ import annotations
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    error: str = ""


class BaseProvider(ABC):
    """Interfaz común para todos los proveedores LLM."""

    @abstractmethod
    def complete(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> LLMResponse:
        """Envía mensajes al LLM y retorna la respuesta con tool_calls si los hay."""
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """Retorna la lista de modelos disponibles en este proveedor."""
        ...
