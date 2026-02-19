"""Demo application for cjm-transcript-workflow-management library.

Standalone management interface for context graph documents.
Lists, inspects, deletes, and imports/exports graph spines.

Run with: python demo_app.py
"""

from pathlib import Path

from fasthtml.common import (
    fast_app, Div, H1, P, Span,
    APIRouter,
)

# Plugin system
from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.scheduling import SafetyScheduler

# DaisyUI components
from cjm_fasthtml_daisyui.core.resources import get_daisyui_headers
from cjm_fasthtml_daisyui.core.testing import create_theme_persistence_script
from cjm_fasthtml_daisyui.components.data_display.badge import (
    badge, badge_colors, badge_styles, badge_sizes
)
from cjm_fasthtml_daisyui.utilities.semantic_colors import text_dui

# Tailwind utilities
from cjm_fasthtml_tailwind.utilities.spacing import p, m
from cjm_fasthtml_tailwind.utilities.sizing import container, max_w
from cjm_fasthtml_tailwind.utilities.typography import font_size, font_weight
from cjm_fasthtml_tailwind.utilities.flexbox_and_grid import (
    flex_display, flex_direction, justify, items, gap,
)
from cjm_fasthtml_tailwind.core.base import combine_classes

# App core
from cjm_fasthtml_app_core.core.routing import register_routes
from cjm_fasthtml_app_core.core.htmx import handle_htmx_request

# Library imports
from cjm_transcript_workflow_management.html_ids import ManagementHtmlIds


# =============================================================================
# Configuration
# =============================================================================

# Path to test graph database
TEST_GRAPH_DB = Path(__file__).parent / "test_files" / "graph.db"

# Graph plugin name
GRAPH_PLUGIN_NAME = "cjm-graph-plugin-sqlite"


# =============================================================================
# Demo Page Renderer
# =============================================================================

def render_demo_page(plugin_manager, plugin_loaded):
    """Create the demo page with placeholder management content."""

    status_text = "Plugin Loaded" if plugin_loaded else "Plugin Not Available"
    status_color = badge_colors.success if plugin_loaded else badge_colors.error

    return Div(
        # Header
        Div(
            H1("Graph Management", cls=combine_classes(font_size._3xl, font_weight.bold)),
            Span(
                status_text,
                cls=combine_classes(badge, badge_styles.outline, badge_sizes.sm, status_color)
            ),
            cls=combine_classes(flex_display, justify.between, items.center, m.b(4))
        ),
        P(
            "Manage context graph documents — list, inspect, delete, and import/export graph spines.",
            cls=combine_classes(text_dui.base_content.opacity(70), m.b(6))
        ),

        # Placeholder for document list (will be replaced in Phase 3)
        Div(
            P(
                f"Graph DB: {TEST_GRAPH_DB}",
                cls=combine_classes(font_size.sm, text_dui.base_content.opacity(60))
            ),
            P(
                f"Database exists: {TEST_GRAPH_DB.exists()}",
                cls=combine_classes(font_size.sm, text_dui.base_content.opacity(60))
            ),
            P(
                "Document list will be rendered here in Phase 3.",
                cls=combine_classes(font_size.sm, text_dui.base_content.opacity(50), m.t(4))
            ),
            id=ManagementHtmlIds.DOCUMENT_LIST,
        ),

        id=ManagementHtmlIds.PAGE_CONTENT,
        cls=combine_classes(
            container, max_w._5xl, m.x.auto,
            flex_display, flex_direction.col,
            p(4), gap(4)
        )
    )


# =============================================================================
# Main Application
# =============================================================================

def main():
    """Initialize the management demo and start the server."""
    print("\n" + "=" * 70)
    print("Initializing cjm-transcript-workflow-management Demo")
    print("=" * 70)

    # Initialize FastHTML app
    app, rt = fast_app(
        pico=False,
        hdrs=[*get_daisyui_headers(), create_theme_persistence_script()],
        title="Graph Management Demo",
        htmlkw={'data-theme': 'light'},
        secret_key="demo-secret-key"
    )

    router = APIRouter(prefix="")

    # -------------------------------------------------------------------------
    # Set up plugin manager
    # -------------------------------------------------------------------------
    print("\n[Plugin System]")

    project_root = Path(__file__).parent
    manifests_dir = project_root / ".cjm" / "manifests"

    plugin_manager = PluginManager(
        scheduler=SafetyScheduler(),
        search_paths=[manifests_dir]
    )
    plugin_manager.discover_manifests()

    # Load the graph plugin with test database
    graph_meta = plugin_manager.get_discovered_meta(GRAPH_PLUGIN_NAME)
    plugin_loaded = False

    if graph_meta:
        try:
            success = plugin_manager.load_plugin(graph_meta, {
                "db_path": str(TEST_GRAPH_DB),
            })
            plugin_loaded = success
            status = "loaded" if success else "failed"
            print(f"  {GRAPH_PLUGIN_NAME}: {status}")
            print(f"  Database: {TEST_GRAPH_DB}")
        except Exception as e:
            print(f"  {GRAPH_PLUGIN_NAME}: error - {e}")
    else:
        print(f"  {GRAPH_PLUGIN_NAME}: not found")

    print(f"  Test database exists: {TEST_GRAPH_DB.exists()}")

    # -------------------------------------------------------------------------
    # Page routes
    # -------------------------------------------------------------------------
    @router
    def index(request):
        """Demo homepage."""
        return handle_htmx_request(
            request,
            lambda: render_demo_page(plugin_manager, plugin_loaded)
        )

    # -------------------------------------------------------------------------
    # Register routes
    # -------------------------------------------------------------------------
    register_routes(app, router)

    # Debug output
    print("\n" + "=" * 70)
    print("Registered Routes:")
    print("=" * 70)
    for route in app.routes:
        if hasattr(route, 'path'):
            print(f"  {route.path}")
    print("=" * 70)
    print("Demo App Ready!")
    print("=" * 70 + "\n")

    return app


if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading

    app = main()

    port = 5035
    host = "0.0.0.0"
    display_host = 'localhost' if host in ['0.0.0.0', '127.0.0.1'] else host

    print(f"Server: http://{display_host}:{port}")
    print()

    timer = threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}"))
    timer.daemon = True
    timer.start()

    uvicorn.run(app, host=host, port=port)
