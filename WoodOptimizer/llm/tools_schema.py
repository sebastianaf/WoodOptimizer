"""
Esquemas de herramientas en formato OpenAI function-calling.
Compatibles con Ollama, Groq, LM Studio, OpenAI y cualquier proveedor compatible.
"""
from __future__ import annotations

TOOLS_SCHEMA: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_parts",
            "description": "Obtiene lista de todas las piezas del modelo FreeCAD activo con sus dimensiones.",
            "parameters": {
                "type": "object",
                "properties": {
                    "material_filter": {
                        "type": "string",
                        "description": "Filtrar por material (opcional, ej: 'melamina_blanco')"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_part",
            "description": "Crea un panel/pieza de madera en el modelo FreeCAD activo.",
            "parameters": {
                "type": "object",
                "required": ["name", "length", "width"],
                "properties": {
                    "name":      {"type": "string",  "description": "Nombre único de la pieza"},
                    "length":    {"type": "number",  "description": "Largo en mm (eje X)"},
                    "width":     {"type": "number",  "description": "Ancho en mm (eje Z)"},
                    "thickness": {"type": "number",  "description": "Espesor en mm, por defecto 18"},
                    "x":         {"type": "number",  "description": "Posición X en mm, por defecto 0"},
                    "y":         {"type": "number",  "description": "Posición Y en mm, por defecto 0"},
                    "z":         {"type": "number",  "description": "Posición Z en mm, por defecto 0"},
                    "material":  {"type": "string",  "description": "Material, por defecto melamina_blanco"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_part",
            "description": "Modifica dimensiones o posición de una pieza existente.",
            "parameters": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name":      {"type": "string", "description": "Nombre de la pieza a modificar"},
                    "length":    {"type": "number"},
                    "width":     {"type": "number"},
                    "thickness": {"type": "number"},
                    "x":         {"type": "number"},
                    "y":         {"type": "number"},
                    "z":         {"type": "number"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_part",
            "description": "Elimina una pieza del modelo.",
            "parameters": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "description": "Nombre de la pieza a eliminar"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_cuts",
            "description": "Corre el algoritmo de optimización de corte sobre las piezas del modelo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet_width":            {"type": "integer", "description": "Ancho del tablero en mm, por defecto 2440"},
                    "sheet_height":           {"type": "integer", "description": "Alto del tablero en mm, por defecto 1220"},
                    "thickness":              {"type": "integer", "description": "Espesor a optimizar en mm, por defecto 18"},
                    "kerf":                   {"type": "integer", "description": "Ancho de sierra en mm, por defecto 3"},
                    "prefer_large_remnants":  {"type": "boolean", "description": "Priorizar retales grandes, por defecto true"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_cut_plan",
            "description": "Obtiene el último plan de corte calculado con posiciones de cada pieza.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_remnants",
            "description": "Lista los retales disponibles registrados para reusar.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_remnant",
            "description": "Registra un retal disponible para usar en la próxima optimización.",
            "parameters": {
                "type": "object",
                "required": ["width", "height", "thickness"],
                "properties": {
                    "width":     {"type": "integer", "description": "Ancho del retal en mm"},
                    "height":    {"type": "integer", "description": "Alto del retal en mm"},
                    "thickness": {"type": "integer", "description": "Espesor del retal en mm"},
                    "label":     {"type": "string",  "description": "Etiqueta opcional"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "export_cutlist",
            "description": "Exporta la lista de corte en el formato especificado.",
            "parameters": {
                "type": "object",
                "required": ["format"],
                "properties": {
                    "format": {"type": "string", "enum": ["csv", "json", "pdf"], "description": "Formato de exportación"},
                    "path":   {"type": "string", "description": "Ruta de salida (opcional)"}
                }
            }
        }
    }
]
