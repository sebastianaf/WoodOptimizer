# WoodOptimizer

FreeCAD workbench for optimizing melamine board cuts and AI-assisted furniture design.

## Features

- **AI design assistant** — chat with Ollama or any OpenAI-compatible API (DeepSeek, Groq, LM Studio, etc.). No dependency on Claude or paid external services.
- **2D guillotine bin packing** — algorithm ported from [OpenCutList](https://github.com/lairdubois/fontobene-go) using BFD + SPLIT_MAXIMIZE_AREA strategy to minimize waste.
- **Embedded MCP server** — the assistant controls FreeCAD directly via MCP (Model Context Protocol) tools over SSE on port 7891. Also accessible from Claude Code or any external MCP client.
- **Offcut management** — register leftover pieces, score by area, persist between sessions, reuse in the next cut plan.
- **Visual diagram** — Qt panel with QPainter drawing each sheet with color-coded pieces.
- **Export** — CSV, JSON and PDF with diagrams.

## Requirements

| Component | Minimum version |
|-----------|----------------|
| FreeCAD | 0.21 |
| Python | 3.9 |
| mcp[cli] | 1.0 |
| reportlab | 3.6 |

For the AI assistant you need **Ollama** running locally, or any OpenAI-compatible API (DeepSeek, Groq, LM Studio…).

## Installation

### From FreeCAD Addon Manager

1. In FreeCAD: **Tools → Addon Manager**
2. Search for "WoodOptimizer"
3. Install and restart FreeCAD

### Manual

```bash
cd ~/.local/share/FreeCAD/Mod/
git clone https://github.com/sebastianaf/WoodOptimizer.git
pip install "mcp[cli]>=1.0" reportlab
# Restart FreeCAD
```

## Quick start

1. Switch to the **WoodOptimizer** workbench in FreeCAD
2. Click **Open panel** to show the side dock
3. Go to the **Settings** tab — choose your provider (Ollama / DeepSeek / OpenAI-compat), set the URL, model and API key, then click **Save**
4. Switch to the **Assistant** tab and type: *"Design a 60×240 cm wardrobe with 3 shelves and a bottom drawer"*
5. The assistant creates the parts in the document and calculates the cut plan
6. **Cut plan** tab: visual diagram + **Export PDF** button
7. **Offcuts** tab: import leftovers from the plan to reuse them next time

### DeepSeek setup

| Field | Value |
|-------|-------|
| Provider | `deepseek` |
| URL | `https://api.deepseek.com/v1` |
| Model | `deepseek-chat` |
| API Key | your key from `platform.deepseek.com` |

### Ollama (local)

```bash
ollama pull qwen2.5-coder:32b
# or any other model
```
Provider: `ollama` · URL: `http://localhost:11434`

## Architecture

```
InitGui.py                   ← FreeCAD entry point
WoodOptimizer/
  core/                      ← pure Python logic (no FreeCAD, CI-testable)
    models.py                    Part, Sheet, CutPlan, Remnant dataclasses
    bin_packing.py               2D guillotine BFD (OpenCutList port)
    geometry.py                  FreeCAD bounding-box extraction
    remnant_manager.py           offcut lifecycle + JSON persistence
  mcp/
    server.py                    FastMCP SSE on port 7891
    handlers.py                  9 MCP tools
    state.py                     global workbench state
  llm/
    client.py                    tool_call → FreeCAD → response loop
    providers/ollama.py          POST /api/chat (no external deps)
    providers/openai_compat.py   POST /v1/chat/completions
    config.py                    saved in FreeCAD prefs / ~/.woodoptimizer_config.json
  ui/
    panel_main.py                QDockWidget with tabs
    panel_chat.py                chat + Stop/Clear/multiline input
    panel_cutplan.py             QPainter diagram + Export PDF
    panel_remnants.py            offcuts table + import from plan
    panel_settings.py            provider/model/key configuration
  commands/
    cmd_open_panel.py            WO_OpenPanel
    cmd_optimize.py              WO_Optimize
    cmd_export.py                WO_Export
  export/
    csv_exporter.py
    json_exporter.py
    pdf_exporter.py              multi-page PDF with reportlab
```

## Using as an external MCP client

The MCP server starts automatically when the workbench is activated. To use it from Claude Code or any other MCP client:

```json
// .mcp.json at the project root
{
  "mcpServers": {
    "freecad-woodoptimizer": {
      "type": "sse",
      "url": "http://localhost:7891/sse"
    }
  }
}
```

Available tools: `get_parts`, `create_part`, `update_part`, `delete_part`, `optimize_cuts`, `get_cut_plan`, `get_remnants`, `add_remnant`, `export_cutlist`.

## Development & tests

```bash
pip install pytest

# Full test suite (111 tests, no FreeCAD required)
python3 -m pytest tests/ -v

# Bin packing demo with ASCII diagram
python3 demo_closet.py
```

## Publishing to the FreeCAD Addon Manager

1. Make sure your repo is public and has `package.xml` at the root (already included).
2. Fork `https://github.com/FreeCAD/FreeCAD-addons`.
3. Add to `package_list.json`:
   ```json
   { "name": "WoodOptimizer", "url": "https://github.com/sebastianaf/WoodOptimizer", "branch": "main" }
   ```
4. Open a PR with title: `Add WoodOptimizer addon`.

## License

LGPL-2.1-or-later — same as FreeCAD.
