# WoodOptimizer

Workbench para FreeCAD que optimiza el corte de tableros de melamina y asiste el diseño de muebles mediante IA local.

## Características

- **Asistente IA de diseño** — chat con Ollama o cualquier API compatible con OpenAI (Groq, LM Studio, etc.). Sin dependencia de Claude ni servicios externos de pago.
- **Optimización 2D guillotine** — algoritmo port de [OpenCutList](https://github.com/lairdubois/fontobene-go) con estrategia BFD + SPLIT_MAXIMIZE_AREA para minimizar desperdicios.
- **Servidor MCP embebido** — el asistente controla FreeCAD directamente mediante herramientas MCP (Model Context Protocol) en SSE port 7891. También accesible desde Claude Code u otro cliente MCP externo.
- **Gestión de retales** — registra piezas sobrantes, puntúa por área, persiste entre sesiones, las reutiliza en el siguiente plan de corte.
- **Diagrama visual** — panel Qt con QPainter que muestra cada tablero con las piezas coloreadas.
- **Exportación** — CSV, JSON y PDF con diagrama.

## Requisitos

| Componente | Versión mínima |
|-----------|---------------|
| FreeCAD | 0.21 |
| Python | 3.9 |
| mcp[cli] | 1.0 |
| reportlab | 3.6 |

Para el asistente IA se necesita **Ollama** corriendo localmente (o cualquier API compatible con OpenAI).

## Instalación

### Desde FreeCAD Addon Manager

1. En FreeCAD: **Herramientas → Addon Manager**
2. Buscar "WoodOptimizer"
3. Instalar y reiniciar FreeCAD

### Manual

```bash
# Clonar en el directorio de addons de FreeCAD
cd ~/.local/share/FreeCAD/Mod/
git clone https://github.com/woodoptimizer/wood-optimizer-wb WoodOptimizer
pip install "mcp[cli]>=1.0" reportlab
```

## Uso rápido

1. Cambiar al workbench **WoodOptimizer** en FreeCAD
2. Clic en **Abrir panel** para mostrar el dock lateral
3. Pestaña **Asistente**: configurar proveedor (Ollama / OpenAI-compat), URL y modelo
4. Escribir: *"Diseñame un armario de 60×240 con 3 entrepaños y cajón inferior"*
5. El asistente crea las piezas en el documento y calcula el plan de corte
6. Pestaña **Plan de corte**: diagrama visual + botón **Exportar PDF**
7. Pestaña **Retales**: importar sobrantes del plan para reutilizarlos la próxima vez

## Arquitectura

```
InitGui.py                   ← entry point FreeCAD
WoodOptimizer/
  core/                      ← lógica pura Python (sin FreeCAD, testeable en CI)
    models.py                    dataclasses: Part, Sheet, CutPlan, Remnant
    bin_packing.py               guillotine 2D BFD (port OpenCutList)
    geometry.py                  extracción de bounding boxes de FreeCAD
    remnant_manager.py           ciclo de vida de retales + persistencia JSON
  mcp/
    server.py                    FastMCP SSE en puerto 7891
    handlers.py                  9 herramientas MCP
    state.py                     estado global del workbench
  llm/
    client.py                    loop tool_call → FreeCAD → respuesta
    providers/ollama.py          POST /api/chat (sin dependencias externas)
    providers/openai_compat.py   POST /v1/chat/completions
    config.py                    config en FreeCAD prefs / ~/.woodoptimizer_config.json
  ui/
    panel_main.py                QDockWidget con pestañas
    panel_chat.py                chat Qt + selector proveedor/modelo
    panel_cutplan.py             diagrama QPainter + exportar PDF
    panel_remnants.py            tabla de retales + importar desde plan
  commands/
    cmd_open_panel.py            WO_OpenPanel
    cmd_optimize.py              WO_Optimize
    cmd_export.py                WO_Export
  export/
    csv_exporter.py
    json_exporter.py
    pdf_exporter.py              diagrama con reportlab
```

## MCP como cliente externo

El servidor MCP arranca automáticamente al activar el workbench. Para usarlo desde Claude Code u otro cliente:

```json
// .mcp.json en la raíz del proyecto
{
  "mcpServers": {
    "freecad-woodoptimizer": {
      "type": "sse",
      "url": "http://localhost:7891/sse"
    }
  }
}
```

Herramientas disponibles: `get_parts`, `create_part`, `update_part`, `delete_part`, `optimize_cuts`, `get_cut_plan`, `get_remnants`, `add_remnant`, `export_cutlist`.

## Desarrollo y tests

```bash
# Instalar dependencias de desarrollo
pip install pytest

# Ejecutar suite completa (99 tests, no requiere FreeCAD)
python3 -m pytest tests/ -v

# Demo de bin packing con diagrama ASCII
python3 demo_closet.py
```

## Licencia

LGPL-2.1-or-later — igual que FreeCAD.
