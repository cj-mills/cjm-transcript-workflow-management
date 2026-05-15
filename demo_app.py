"""Demo application for cjm-transcript-workflow-management library.

Standalone management interface for context graph documents.
Lists, inspects, deletes, and imports/exports graph spines.

Run with: python demo_app.py
"""

from pathlib import Path

from fasthtml.common import (
    fast_app, Div, H1, P, Span,
)

from cjm_fasthtml_app_core.core.routing import APIRouter

# Plugin system
from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.scheduling import SafetyScheduler

# DaisyUI components
from cjm_fasthtml_daisyui.core.resources import get_daisyui_headers
from cjm_fasthtml_daisyui.core.testing import create_theme_persistence_script

# App core
from cjm_fasthtml_app_core.core.routing import register_routes
from cjm_fasthtml_app_core.core.htmx import handle_htmx_request

# Library imports
from cjm_transcript_workflow_management.services.management import ManagementService
from cjm_transcript_workflow_management.routes.init import init_management_routers


# =============================================================================
# Configuration
# =============================================================================

# Path to test graph database
TEST_GRAPH_DB = Path(__file__).parent / "test_files" / "graph.db"

# Graph plugin name
GRAPH_PLUGIN_NAME = "cjm-graph-plugin-sqlite"


# =============================================================================
# Main Application
# =============================================================================

def main():
    """Initialize the management demo and start the server."""
    print("\n" + "=" * 70)
    print("Initializing cjm-transcript-workflow-management Demo")
    print("=" * 70)

    # Initialize FastHTML app
    APP_ID = "txwfmgmt"

    app, rt = fast_app(
        pico=False,
        hdrs=[*get_daisyui_headers(), create_theme_persistence_script()],
        title="Graph Management Demo",
        htmlkw={'data-theme': 'light'},
        session_cookie=f'session_{APP_ID}_',
        secret_key=f'{APP_ID}-demo-secret',
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
    # Create service and routes
    # -------------------------------------------------------------------------
    service = ManagementService(plugin_manager, GRAPH_PLUGIN_NAME)
    print(f"\n[Management Service]")
    print(f"  Available: {service.is_available()}")

    mgmt_result = init_management_routers(
        service=service,
        prefix="/manage",
    )

    print(f"\n[Management URLs]")
    print(f"  management_page: {mgmt_result.urls.management_page}")
    print(f"  list_documents: {mgmt_result.urls.list_documents}")
    print(f"  document_detail: {mgmt_result.urls.document_detail}")
    print(f"  delete_document: {mgmt_result.urls.delete_document}")
    print(f"  delete_selected: {mgmt_result.urls.delete_selected}")
    print(f"  export_document: {mgmt_result.urls.export_document}")
    print(f"  export_all: {mgmt_result.urls.export_all}")
    print(f"  import_graph: {mgmt_result.urls.import_graph}")

    # -------------------------------------------------------------------------
    # Page routes
    # -------------------------------------------------------------------------
    @router
    async def index(request):
        """Demo homepage — loads document list on page load."""
        await mgmt_result.refresh_items()
        return handle_htmx_request(
            request,
            mgmt_result.render_page
        )

    # -------------------------------------------------------------------------
    # Register routes
    # -------------------------------------------------------------------------
    register_routes(app, router)
    for mgmt_router in mgmt_result.routers:
        register_routes(app, mgmt_router)

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
