"""Manual test script for ManagementService.

Tests all service methods against test_files/graph.db which contains:
- 12 Document nodes (all titled "Short Test Audio", media_type "audio")
- 132 Segment nodes (11 segments per document)
- Edges: 12 STARTS_WITH, 120 NEXT, 132 PART_OF

Run with: conda run -n cjm-transcript-workflow-management python tests_manual/test_management_service.py
"""

import asyncio
import json
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from cjm_plugin_system.core.manager import PluginManager
from cjm_plugin_system.core.scheduling import SafetyScheduler

from cjm_transcript_workflow_management.services.management import (
    ManagementService, DEBUG_MANAGEMENT_SERVICE
)


# =============================================================================
# Setup
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
GRAPH_PLUGIN_NAME = "cjm-graph-plugin-sqlite"
ORIGINAL_DB = PROJECT_ROOT / "test_files" / "graph.db"
MANIFESTS_DIR = PROJECT_ROOT / ".cjm" / "manifests"


def setup_service(db_path: Path) -> ManagementService:
    """Create a ManagementService with a fresh plugin manager."""
    manager = PluginManager(
        scheduler=SafetyScheduler(),
        search_paths=[MANIFESTS_DIR]
    )
    manager.discover_manifests()
    meta = manager.get_discovered_meta(GRAPH_PLUGIN_NAME)
    assert meta is not None, f"Plugin {GRAPH_PLUGIN_NAME} not found"
    success = manager.load_plugin(meta, {"db_path": str(db_path)})
    assert success, f"Failed to load {GRAPH_PLUGIN_NAME}"
    return ManagementService(manager)


def copy_test_db() -> Path:
    """Copy graph.db to a temp file so tests can modify it safely."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    shutil.copy2(ORIGINAL_DB, tmp.name)
    return Path(tmp.name)


# =============================================================================
# Tests
# =============================================================================

async def test_is_available(svc: ManagementService):
    """Test plugin availability check."""
    print("\n--- test_is_available ---")
    assert svc.is_available(), "Service should be available"
    print("  PASS: is_available() returns True")


async def test_list_documents(svc: ManagementService):
    """Test listing all documents."""
    print("\n--- test_list_documents ---")
    docs = await svc.list_documents_async()

    assert len(docs) == 12, f"Expected 12 documents, got {len(docs)}"
    print(f"  Found {len(docs)} documents")

    # All should be titled "Short Test Audio"
    for d in docs:
        assert d.title == "Short Test Audio", f"Unexpected title: {d.title}"
        assert d.media_type == "audio", f"Unexpected media_type: {d.media_type}"
        assert d.segment_count == 11, f"Expected 11 segments, got {d.segment_count}"

    # Should be sorted newest first (all same created_at is fine)
    print(f"  First doc: {docs[0].title}, {docs[0].segment_count} segs, "
          f"duration={docs[0].total_duration:.1f}s")
    print("  PASS: All 12 documents with correct attributes")


async def test_get_document_detail(svc: ManagementService):
    """Test getting full document detail."""
    print("\n--- test_get_document_detail ---")

    # Get a valid document ID from list
    docs = await svc.list_documents_async()
    doc_id = docs[0].document_id
    detail = await svc.get_document_detail_async(doc_id)

    assert detail is not None, "Detail should not be None"
    assert detail.document_id == doc_id
    assert detail.segment_count == 11
    assert detail.has_starts_with, "Should have STARTS_WITH edge"
    assert detail.next_chain_complete, "NEXT chain should be complete"
    assert detail.next_count == 10, f"Expected 10 NEXT edges, got {detail.next_count}"
    assert detail.part_of_complete, "PART_OF should be complete"
    assert detail.part_of_count == 11, f"Expected 11 PART_OF edges, got {detail.part_of_count}"
    assert detail.all_have_timing, "All segments should have timing"
    assert detail.all_have_sources, "All segments should have sources"
    assert detail.all_checks_passed, "All integrity checks should pass"
    assert len(detail.first_segments) == 3, f"Expected 3 first samples, got {len(detail.first_segments)}"
    assert len(detail.last_segments) == 3, f"Expected 3 last samples, got {len(detail.last_segments)}"
    assert detail.first_segments[0].index == 0
    assert detail.total_duration > 0

    print(f"  Title: {detail.title}")
    print(f"  Segments: {detail.segment_count}, Duration: {detail.total_duration:.1f}s")
    print(f"  Integrity: all_checks_passed={detail.all_checks_passed}")
    print(f"  Sources: {detail.source_plugins}")
    print(f"  First sample: [{detail.first_segments[0].index}] \"{detail.first_segments[0].text}\"")
    print("  PASS: Detail computed correctly")

    # Test invalid ID
    bad_detail = await svc.get_document_detail_async("nonexistent-id")
    assert bad_detail is None, "Should return None for invalid ID"
    print("  PASS: Returns None for invalid ID")


async def test_export_document(svc: ManagementService):
    """Test exporting a single document."""
    print("\n--- test_export_document ---")

    docs = await svc.list_documents_async()
    doc_id = docs[0].document_id
    bundle = await svc.export_document_async(doc_id)

    assert bundle is not None, "Bundle should not be None"
    assert bundle.format == "cjm-context-graph"
    assert bundle.version == "1.0.0"
    assert bundle.document_count == 1
    assert bundle.source_plugin == GRAPH_PLUGIN_NAME
    assert "nodes" in bundle.graph
    assert "edges" in bundle.graph

    nodes = bundle.graph["nodes"]
    edges = bundle.graph["edges"]
    doc_nodes = [n for n in nodes if n.get("label") == "Document"]
    seg_nodes = [n for n in nodes if n.get("label") == "Segment"]

    assert len(doc_nodes) == 1, f"Expected 1 Document node, got {len(doc_nodes)}"
    assert len(seg_nodes) == 11, f"Expected 11 Segment nodes, got {len(seg_nodes)}"

    print(f"  Exported: {len(nodes)} nodes, {len(edges)} edges")
    print(f"  Format: {bundle.format} v{bundle.version}")

    # Verify JSON round-trip
    bundle_dict = asdict(bundle)
    json_str = json.dumps(bundle_dict, indent=2)
    parsed = json.loads(json_str)
    assert parsed["format"] == "cjm-context-graph"
    print(f"  JSON size: {len(json_str)} bytes")
    print("  PASS: Export produces valid bundle")


async def test_export_all(svc: ManagementService):
    """Test exporting the entire database."""
    print("\n--- test_export_all ---")

    bundle = await svc.export_all_async()

    assert bundle is not None, "Bundle should not be None"
    assert bundle.document_count == 12, f"Expected 12 documents, got {bundle.document_count}"

    nodes = bundle.graph["nodes"]
    edges = bundle.graph["edges"]
    doc_nodes = [n for n in nodes if n.get("label") == "Document"]
    seg_nodes = [n for n in nodes if n.get("label") == "Segment"]

    assert len(doc_nodes) == 12
    assert len(seg_nodes) == 132

    print(f"  Exported: {len(nodes)} nodes ({len(doc_nodes)} docs, {len(seg_nodes)} segs)")
    print(f"  Edges: {len(edges)}")
    print("  PASS: Full database export correct")


async def test_delete_document(svc: ManagementService):
    """Test deleting a single document (uses copy of DB)."""
    print("\n--- test_delete_document ---")

    # List before delete
    docs_before = await svc.list_documents_async()
    assert len(docs_before) == 12
    target_id = docs_before[0].document_id

    # Delete one document
    result = await svc.delete_document_async(target_id)
    assert result is True, "Delete should return True"

    # List after delete
    docs_after = await svc.list_documents_async()
    assert len(docs_after) == 11, f"Expected 11 docs after delete, got {len(docs_after)}"
    remaining_ids = [d.document_id for d in docs_after]
    assert target_id not in remaining_ids, "Deleted doc should not appear in list"

    print(f"  Deleted document {target_id[:8]}...")
    print(f"  Documents: {len(docs_before)} -> {len(docs_after)}")
    print("  PASS: Single delete works with cascade")


async def test_delete_documents_bulk(svc: ManagementService):
    """Test bulk delete (continues from test_delete_document state: 11 docs)."""
    print("\n--- test_delete_documents_bulk ---")

    docs = await svc.list_documents_async()
    count_before = len(docs)
    # Delete first 3 documents
    ids_to_delete = [d.document_id for d in docs[:3]]

    deleted = await svc.delete_documents_async(ids_to_delete)
    assert deleted > 0, "Should have deleted some nodes"

    docs_after = await svc.list_documents_async()
    assert len(docs_after) == count_before - 3, \
        f"Expected {count_before - 3} docs, got {len(docs_after)}"

    print(f"  Bulk deleted 3 documents ({deleted} nodes removed)")
    print(f"  Documents: {count_before} -> {len(docs_after)}")
    print("  PASS: Bulk delete works")

    # Test empty list
    result = await svc.delete_documents_async([])
    assert result == 0, "Empty list should return 0"
    print("  PASS: Empty list returns 0")


async def test_import_graph(svc: ManagementService):
    """Test import after deleting all docs (round-trip test)."""
    print("\n--- test_import_graph ---")

    # Export remaining before deleting
    bundle = await svc.export_all_async()
    assert bundle is not None
    bundle_dict = asdict(bundle)
    docs_in_export = bundle.document_count
    print(f"  Exported {docs_in_export} documents for re-import")

    # Delete all remaining
    docs = await svc.list_documents_async()
    all_ids = [d.document_id for d in docs]
    await svc.delete_documents_async(all_ids)

    docs_empty = await svc.list_documents_async()
    assert len(docs_empty) == 0, "Database should be empty after deleting all"
    print("  Database emptied")

    # Import the exported data
    result = await svc.import_graph_async(bundle_dict, merge_strategy="skip")
    assert result.success, f"Import should succeed, errors: {result.errors}"
    assert result.nodes_created > 0, "Should have created nodes"
    assert result.edges_created > 0, "Should have created edges"

    print(f"  Imported: {result.nodes_created} nodes, {result.edges_created} edges")

    # Verify documents exist again
    docs_after = await svc.list_documents_async()
    assert len(docs_after) == docs_in_export, \
        f"Expected {docs_in_export} docs after import, got {len(docs_after)}"
    print(f"  Documents after import: {len(docs_after)}")
    print("  PASS: Import round-trip works")


async def test_import_validation(svc: ManagementService):
    """Test import validation for invalid data."""
    print("\n--- test_import_validation ---")

    # Invalid format
    result = await svc.import_graph_async({"format": "wrong", "version": "1.0.0", "graph": {}})
    assert not result.success
    assert len(result.errors) > 0
    print(f"  Invalid format: {result.errors[0]}")

    # Invalid version
    result = await svc.import_graph_async({"format": "cjm-context-graph", "version": "2.0.0", "graph": {}})
    assert not result.success
    print(f"  Invalid version: {result.errors[0]}")

    # Missing graph field
    result = await svc.import_graph_async({"format": "cjm-context-graph", "version": "1.0.0"})
    assert not result.success
    print(f"  Missing graph: {result.errors[0]}")

    print("  PASS: All validation cases handled")


# =============================================================================
# Runner
# =============================================================================

async def run_all_tests():
    """Run all tests using a copy of the test database."""
    assert ORIGINAL_DB.exists(), f"Test database not found: {ORIGINAL_DB}"

    # Copy DB so we can safely modify it
    db_copy = copy_test_db()
    print(f"Using temp database: {db_copy}")

    try:
        svc = setup_service(db_copy)

        # Read-only tests first
        await test_is_available(svc)
        await test_list_documents(svc)
        await test_get_document_detail(svc)
        await test_export_document(svc)
        await test_export_all(svc)

        # Mutating tests (order matters)
        await test_delete_document(svc)
        await test_delete_documents_bulk(svc)
        await test_import_graph(svc)
        await test_import_validation(svc)

        print("\n" + "=" * 50)
        print("ALL TESTS PASSED")
        print("=" * 50)

    finally:
        # Cleanup temp DB
        db_copy.unlink(missing_ok=True)
        print(f"\nCleaned up temp database: {db_copy}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
