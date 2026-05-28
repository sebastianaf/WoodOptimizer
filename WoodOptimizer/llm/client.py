from __future__ import annotations
import json
import logging
from typing import Callable, Iterator
from .providers.base import BaseProvider, LLMResponse, ToolCall
from .tools_schema import TOOLS_SCHEMA

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10  # evita loops infinitos

SYSTEM_PROMPT_DESIGNER = """Eres un asistente especializado en diseño de muebles de melamina.
Tienes acceso a herramientas para crear y modificar piezas directamente en FreeCAD.

Reglas:
- Cuando el usuario pida un mueble, usa las herramientas para construirlo paso a paso.
- Usa siempre espesor 18mm para melamina estándar salvo que se indique otro valor.
- Los nombres de piezas deben ser únicos y descriptivos (ej: lateral_izq, techo, entrepano_1).
- Después de crear todas las piezas, llama a optimize_cuts para generar el plan de corte.
- Responde en español, de forma clara y concisa.
- Cuando ejecutes herramientas, describe brevemente lo que estás haciendo."""


def _build_dispatch() -> dict[str, Callable]:
    """Importa los handlers en tiempo de ejecución para evitar importaciones circulares."""
    from ..mcp.handlers import (
        handle_get_parts, handle_create_part, handle_update_part,
        handle_delete_part, handle_optimize_cuts, handle_get_cut_plan,
        handle_get_remnants, handle_add_remnant, handle_export_cutlist,
    )
    return {
        "get_parts":      handle_get_parts,
        "create_part":    handle_create_part,
        "update_part":    handle_update_part,
        "delete_part":    handle_delete_part,
        "optimize_cuts":  handle_optimize_cuts,
        "get_cut_plan":   handle_get_cut_plan,
        "get_remnants":   handle_get_remnants,
        "add_remnant":    handle_add_remnant,
        "export_cutlist": handle_export_cutlist,
    }


def execute_tool(name: str, arguments: dict) -> str:
    """Ejecuta una herramienta MCP y retorna el resultado como JSON string."""
    dispatch = _build_dispatch()
    if name not in dispatch:
        return json.dumps({"error": f"Herramienta '{name}' no encontrada"})
    try:
        result = dispatch[name](**arguments)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error ejecutando herramienta '%s'", name)
        return json.dumps({"error": str(e)})


class LLMClient:
    """
    Cliente LLM provider-agnostic que ejecuta el loop tool_call → FreeCAD → respuesta.
    Soporta Ollama y cualquier API compatible con OpenAI.
    NO incluye Claude directo — usar Claude Code vía MCP externo en su lugar.
    """

    def __init__(self, provider: BaseProvider, model: str):
        self.provider = provider
        self.model = model

    @classmethod
    def from_config(cls) -> "LLMClient":
        """Crea el cliente a partir de la configuración guardada."""
        from .config import load_config
        from .providers.ollama import OllamaProvider
        from .providers.openai_compat import OpenAICompatProvider

        cfg = load_config()
        if cfg.provider == "ollama":
            provider = OllamaProvider(url=cfg.url)
        else:
            provider = OpenAICompatProvider(url=cfg.url, api_key=cfg.api_key)
        return cls(provider=provider, model=cfg.model)

    def chat(
        self,
        message: str,
        history: list[dict],
        on_tool_call: Callable[[str, dict, str], None] | None = None,
    ) -> tuple[str, list[dict]]:
        """
        Envía un mensaje y ejecuta el loop tool_call → resultado → respuesta.

        Args:
            message:     Mensaje del usuario.
            history:     Historial previo [{"role": ..., "content": ...}].
            on_tool_call: Callback opcional llamado en cada tool_call.
                          Firma: (tool_name, arguments, result_json) -> None.

        Returns:
            (texto_final, historial_actualizado)
        """
        messages = list(history) + [{"role": "user", "content": message}]

        for _round in range(MAX_TOOL_ROUNDS):
            response: LLMResponse = self.provider.complete(
                model=self.model,
                messages=messages,
                tools=TOOLS_SCHEMA,
                system=SYSTEM_PROMPT_DESIGNER,
            )

            if response.error:
                error_msg = f"Error del proveedor LLM: {response.error}"
                messages.append({"role": "assistant", "content": error_msg})
                return error_msg, messages

            if not response.tool_calls:
                # Respuesta final de texto
                messages.append({"role": "assistant", "content": response.text})
                return response.text, messages

            # Hay tool_calls — ejecutarlos y continuar
            assistant_msg: dict = {
                "role": "assistant",
                "content": response.text or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in response.tool_calls
                ],
            }
            messages.append(assistant_msg)

            for tc in response.tool_calls:
                result_json = execute_tool(tc.name, tc.arguments)
                logger.debug("Tool %s(%s) → %s", tc.name, tc.arguments, result_json[:200])

                if on_tool_call:
                    on_tool_call(tc.name, tc.arguments, result_json)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_json,
                })

        # Límite de rondas alcanzado
        final = "Se alcanzó el límite de llamadas a herramientas."
        messages.append({"role": "assistant", "content": final})
        return final, messages

    def stream_chat(
        self,
        message: str,
        history: list[dict],
        on_tool_call: Callable[[str, dict, str], None] | None = None,
        tool_executor: Callable[[str, dict], str] | None = None,
    ) -> Iterator[str]:
        """
        Versión generadora de chat() — emite fragmentos de texto a medida que
        se ejecutan herramientas. Útil para actualizar la UI progresivamente.
        """
        messages = list(history) + [{"role": "user", "content": message}]

        for _round in range(MAX_TOOL_ROUNDS):
            response = self.provider.complete(
                model=self.model,
                messages=messages,
                tools=TOOLS_SCHEMA,
                system=SYSTEM_PROMPT_DESIGNER,
            )

            if response.error:
                yield f"\n⚠ Error: {response.error}"
                return

            if not response.tool_calls:
                if response.text:
                    yield response.text
                messages.append({"role": "assistant", "content": response.text})
                return

            if response.text:
                yield response.text

            assistant_msg: dict = {
                "role": "assistant",
                "content": response.text or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in response.tool_calls
                ],
            }
            messages.append(assistant_msg)

            _run_tool = tool_executor or execute_tool
            for tc in response.tool_calls:
                yield f"\n⚙ `{tc.name}`..."
                result_json = _run_tool(tc.name, tc.arguments)

                if on_tool_call:
                    on_tool_call(tc.name, tc.arguments, result_json)

                result = json.loads(result_json)
                if "error" in result:
                    yield f" ✗ {result['error']}\n"
                else:
                    yield f" ✓\n"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_json,
                })

        yield "\n⚠ Límite de rondas alcanzado."
