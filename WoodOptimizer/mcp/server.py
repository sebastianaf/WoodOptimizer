from __future__ import annotations
import threading
import logging
from mcp.server.fastmcp import FastMCP
from .handlers import (
    handle_get_parts, handle_create_part, handle_update_part,
    handle_delete_part, handle_optimize_cuts, handle_get_cut_plan,
    handle_get_remnants, handle_add_remnant, handle_export_cutlist,
)

logger = logging.getLogger(__name__)

_server_thread: threading.Thread | None = None


def _build_app(host: str, port: int) -> FastMCP:
    """Crea y configura la aplicación FastMCP con todas las herramientas."""
    app = FastMCP(
        "freecad-woodoptimizer",
        instructions=(
            "Asistente de diseño de muebles de melamina integrado con FreeCAD. "
            "Usa las herramientas para crear piezas, optimizar cortes y gestionar retales."
        ),
        host=host,
        port=port,
        log_level="WARNING",
    )

    @app.tool()
    def get_parts(material_filter: str = "") -> list[dict]:
        """Obtiene lista de todas las piezas del modelo FreeCAD activo con sus dimensiones."""
        return handle_get_parts(material_filter or None)

    @app.tool()
    def create_part(
        name: str,
        length: float,
        width: float,
        thickness: float = 18,
        x: float = 0,
        y: float = 0,
        z: float = 0,
        material: str = "melamina_blanco",
    ) -> dict:
        """Crea un panel/pieza de madera en el modelo FreeCAD activo."""
        return handle_create_part(name, length, width, thickness, x, y, z, material)

    @app.tool()
    def update_part(
        name: str,
        length: float | None = None,
        width: float | None = None,
        thickness: float | None = None,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
    ) -> dict:
        """Modifica dimensiones o posición de una pieza existente."""
        return handle_update_part(name, length, width, thickness, x, y, z)

    @app.tool()
    def delete_part(name: str) -> dict:
        """Elimina una pieza del modelo."""
        return handle_delete_part(name)

    @app.tool()
    def optimize_cuts(
        sheet_width: int = 2440,
        sheet_height: int = 1220,
        thickness: int = 18,
        kerf: int = 3,
        prefer_large_remnants: bool = True,
    ) -> dict:
        """Corre el algoritmo de optimización de corte sobre las piezas del modelo."""
        return handle_optimize_cuts(sheet_width, sheet_height, thickness, kerf, prefer_large_remnants)

    @app.tool()
    def get_cut_plan() -> dict:
        """Obtiene el último plan de corte calculado."""
        return handle_get_cut_plan()

    @app.tool()
    def get_remnants() -> list[dict]:
        """Lista los retales disponibles registrados."""
        return handle_get_remnants()

    @app.tool()
    def add_remnant(
        width: int,
        height: int,
        thickness: int,
        label: str = "",
    ) -> dict:
        """Registra un retal disponible para usar en la optimización."""
        return handle_add_remnant(width, height, thickness, label)

    @app.tool()
    def export_cutlist(format: str, path: str = "") -> dict:
        """Exporta la lista de corte. Formatos: csv, json."""
        return handle_export_cutlist(format, path or None)

    return app


def start_mcp_server(host: str = "localhost", port: int = 7891) -> int:
    """
    Arranca el servidor MCP con transporte SSE en un thread daemon.
    Retorna el puerto donde escucha.
    Llamado desde InitGui.WoodOptimizerWorkbench.Activated().
    """
    global _server_thread

    if _server_thread and _server_thread.is_alive():
        logger.info("Servidor MCP ya está corriendo en puerto %d", port)
        return port

    app = _build_app(host, port)

    _server_thread = threading.Thread(
        target=app.run,
        kwargs={"transport": "sse"},
        daemon=True,
        name="WoodOptimizer-MCP",
    )
    _server_thread.start()
    logger.info("Servidor MCP iniciado en http://%s:%d/sse", host, port)
    return port
