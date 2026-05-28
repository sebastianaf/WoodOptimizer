"""Tests del LLMClient y proveedores con HTTP mockeado."""
import json
import sys
import types
import pytest

from WoodOptimizer.llm.providers.base import BaseProvider, LLMResponse, ToolCall
from WoodOptimizer.llm.client import LLMClient, execute_tool, MAX_TOOL_ROUNDS
from WoodOptimizer.mcp import state as state_module


# ─── Mock de FreeCAD (igual que en los otros tests) ──────────────────────────

def _make_freecad_mock():
    fc = types.ModuleType("FreeCAD")

    class Vector:
        def __init__(self, x=0, y=0, z=0):
            self.x, self.y, self.z = x, y, z

    class Placement:
        def __init__(self):
            self.Base = Vector()

    class BoundBox:
        def __init__(self, xl, yl, zl):
            self.XLength, self.YLength, self.ZLength = xl, yl, zl

    class Shape:
        def __init__(self, xl=0, yl=0, zl=0, null=False):
            self._null = null
            self.BoundBox = BoundBox(xl, yl, zl)
        def isNull(self): return self._null

    class FreeCADObject:
        def __init__(self, name, label, xl, yl, zl):
            self.Name, self.Label = name, label
            self.Shape = Shape(xl, yl, zl)
            self.Placement = Placement()
            self.Length, self.Width, self.Height = xl, yl, zl

    class Document:
        def __init__(self, objects=None):
            self.Objects = list(objects or [])
            self._map = {o.Name: o for o in self.Objects}
        def addObject(self, t, n):
            obj = FreeCADObject(n, n, 0, 0, 0)
            self.Objects.append(obj); self._map[n] = obj; return obj
        def getObject(self, n): return self._map.get(n)
        def removeObject(self, n):
            o = self._map.pop(n, None)
            if o and o in self.Objects: self.Objects.remove(o)
        def recompute(self): pass

    fc.Vector = Vector
    fc._Document = Document
    fc._Object = FreeCADObject
    fc.ActiveDocument = None
    return fc


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    mock_fc = _make_freecad_mock()
    monkeypatch.setitem(sys.modules, "FreeCAD", mock_fc)
    for mod in ["WoodOptimizer.core.geometry", "WoodOptimizer.mcp.handlers"]:
        if mod in sys.modules:
            monkeypatch.delitem(sys.modules, mod)

    doc = mock_fc._Document(objects=[
        mock_fc._Object("lat_1", "Lateral", 400, 18, 2400),
        mock_fc._Object("lat_2", "Lateral", 400, 18, 2400),
        mock_fc._Object("tec",   "Techo",   564, 18,  400),
    ])
    monkeypatch.setattr(state_module, "_state",
                        state_module.WorkbenchState(doc=doc, remnants=[]))
    yield mock_fc


# ─── Provider mock ────────────────────────────────────────────────────────────

class MockProvider(BaseProvider):
    """Provider de prueba: devuelve respuestas predefinidas."""

    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def complete(self, model, messages, tools=None, system=None) -> LLMResponse:
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        if self._responses:
            return self._responses.pop(0)
        return LLMResponse(text="[fin]")

    def list_models(self) -> list[str]:
        return ["mock-model-1", "mock-model-2"]


# ─── Tests de execute_tool ────────────────────────────────────────────────────

def test_execute_tool_get_parts():
    result = json.loads(execute_tool("get_parts", {}))
    assert isinstance(result, list)
    assert len(result) == 3  # lat_1, lat_2, tec


def test_execute_tool_unknown():
    result = json.loads(execute_tool("tool_inexistente", {}))
    assert "error" in result


def test_execute_tool_create_part():
    result = json.loads(execute_tool("create_part", {
        "name": "nuevo", "length": 600, "width": 400, "thickness": 18
    }))
    assert result["created"] == "nuevo"


def test_execute_tool_error_returns_json():
    result = json.loads(execute_tool("delete_part", {"name": "no_existe"}))
    assert "error" in result


# ─── Tests de LLMClient.chat ──────────────────────────────────────────────────

def test_chat_simple_text_response():
    provider = MockProvider([LLMResponse(text="Hola, soy el asistente.")])
    client = LLMClient(provider=provider, model="test-model")

    text, history = client.chat("Hola", [])

    assert "Hola" in text or "asistente" in text
    assert len(history) == 2  # user + assistant
    assert history[-1]["role"] == "assistant"


def test_chat_adds_user_message_to_history():
    provider = MockProvider([LLMResponse(text="Respuesta")])
    client = LLMClient(provider=provider, model="test")

    _, history = client.chat("Mensaje de prueba", [])
    assert history[0] == {"role": "user", "content": "Mensaje de prueba"}


def test_chat_with_tool_call_executes_and_continues():
    """El cliente debe ejecutar tool_calls y hacer una segunda llamada al LLM."""
    provider = MockProvider([
        LLMResponse(
            text="",
            tool_calls=[ToolCall(id="1", name="get_parts", arguments={})]
        ),
        LLMResponse(text="Encontré 3 piezas en el modelo."),
    ])
    client = LLMClient(provider=provider, model="test")

    text, history = client.chat("¿Qué piezas hay?", [])

    assert "3" in text or "Encontré" in text
    assert len(provider.calls) == 2  # dos llamadas al LLM


def test_chat_tool_result_added_to_messages():
    """El resultado de la herramienta debe añadirse al historial como rol 'tool'."""
    provider = MockProvider([
        LLMResponse(tool_calls=[ToolCall(id="tc1", name="get_parts", arguments={})]),
        LLMResponse(text="Listo."),
    ])
    client = LLMClient(provider=provider, model="test")
    _, history = client.chat("Lista las piezas", [])

    tool_msgs = [m for m in history if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "tc1"


def test_chat_multiple_tool_calls_in_one_response():
    """Múltiples tool_calls en una misma respuesta deben ejecutarse todos."""
    provider = MockProvider([
        LLMResponse(tool_calls=[
            ToolCall(id="1", name="get_parts", arguments={}),
            ToolCall(id="2", name="get_remnants", arguments={}),
        ]),
        LLMResponse(text="Ejecuté 2 herramientas."),
    ])
    client = LLMClient(provider=provider, model="test")
    _, history = client.chat("Info", [])

    tool_msgs = [m for m in history if m.get("role") == "tool"]
    assert len(tool_msgs) == 2


def test_chat_respects_max_tool_rounds():
    """Si el LLM sigue generando tool_calls infinitamente, el loop debe cortarse."""
    infinite_calls = [
        LLMResponse(tool_calls=[ToolCall(id=str(i), name="get_parts", arguments={})])
        for i in range(MAX_TOOL_ROUNDS + 5)
    ]
    provider = MockProvider(infinite_calls)
    client = LLMClient(provider=provider, model="test")

    text, _ = client.chat("loop", [])
    assert "límite" in text.lower()
    assert len(provider.calls) == MAX_TOOL_ROUNDS


def test_chat_provider_error_returns_error_message():
    provider = MockProvider([LLMResponse(text="", error="Connection refused")])
    client = LLMClient(provider=provider, model="test")

    text, _ = client.chat("Hola", [])
    assert "Error" in text or "error" in text.lower()


def test_chat_preserves_existing_history():
    prior = [
        {"role": "user", "content": "anterior"},
        {"role": "assistant", "content": "respuesta anterior"},
    ]
    provider = MockProvider([LLMResponse(text="Ok")])
    client = LLMClient(provider=provider, model="test")

    _, history = client.chat("nuevo mensaje", prior)
    # El historial nuevo debe incluir el previo + nuevo user + assistant
    assert history[0]["content"] == "anterior"
    assert len(history) == 4


def test_chat_on_tool_call_callback_fired():
    """El callback on_tool_call debe llamarse para cada herramienta ejecutada."""
    provider = MockProvider([
        LLMResponse(tool_calls=[ToolCall(id="1", name="get_parts", arguments={})]),
        LLMResponse(text="Hecho."),
    ])
    client = LLMClient(provider=provider, model="test")
    calls_received = []

    def cb(name, args, result):
        calls_received.append(name)

    client.chat("lista", [], on_tool_call=cb)
    assert "get_parts" in calls_received


# ─── Tests de stream_chat ─────────────────────────────────────────────────────

def test_stream_chat_yields_text():
    provider = MockProvider([LLMResponse(text="Texto en streaming.")])
    client = LLMClient(provider=provider, model="test")

    fragments = list(client.stream_chat("hola", []))
    full = "".join(fragments)
    assert "Texto" in full


def test_stream_chat_yields_tool_indicator():
    provider = MockProvider([
        LLMResponse(tool_calls=[ToolCall(id="1", name="get_parts", arguments={})]),
        LLMResponse(text="Listo"),
    ])
    client = LLMClient(provider=provider, model="test")

    fragments = list(client.stream_chat("lista", []))
    full = "".join(fragments)
    assert "get_parts" in full


# ─── Tests de config ──────────────────────────────────────────────────────────

def test_config_save_and_load(tmp_path, monkeypatch):
    from WoodOptimizer.llm import config as config_mod
    monkeypatch.setattr(config_mod, "_CONFIG_PATH", str(tmp_path / "cfg.json"))

    from WoodOptimizer.llm.config import ProviderConfig, save_config, load_config
    cfg = ProviderConfig(provider="openai_compat", url="http://groq.example.com",
                         model="llama3-70b", api_key="sk-test")
    save_config(cfg)
    loaded = load_config()

    assert loaded.provider == "openai_compat"
    assert loaded.url == "http://groq.example.com"
    assert loaded.model == "llama3-70b"


def test_config_defaults_when_no_file(tmp_path, monkeypatch):
    from WoodOptimizer.llm import config as config_mod
    monkeypatch.setattr(config_mod, "_CONFIG_PATH", str(tmp_path / "nonexistent.json"))

    from WoodOptimizer.llm.config import load_config
    cfg = load_config()
    assert cfg.provider == "ollama"
    assert "11434" in cfg.url


# ─── Tests de list_models ─────────────────────────────────────────────────────

def test_list_models_mock():
    provider = MockProvider([])
    assert "mock-model-1" in provider.list_models()


def test_ollama_list_models_handles_error(monkeypatch):
    from WoodOptimizer.llm.providers.ollama import OllamaProvider
    prov = OllamaProvider(url="http://localhost:9999")  # puerto inválido
    models = prov.list_models()
    assert models == []  # debe devolver lista vacía, no lanzar excepción


def test_openai_list_models_handles_error(monkeypatch):
    from WoodOptimizer.llm.providers.openai_compat import OpenAICompatProvider
    prov = OpenAICompatProvider(url="http://localhost:9999")
    models = prov.list_models()
    assert models == []
