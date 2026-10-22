from pathlib import Path

import pytest

from backend.app.domain.assets import ParseStatus
from backend.app.services.asset_inventory import AssetInventory


def test_markdown_inventory_preserves_line_locations_and_hash(tmp_path: Path):
    source = tmp_path / "paper.md"
    source.write_text(
        "# Title\n\nA paragraph with evidence.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```python\nprint(1)\n```\n",
        encoding="utf-8",
    )

    result = AssetInventory(tmp_path / "data").inspect(source)

    assert result.status is ParseStatus.PARSED
    assert result.sha256
    assert result.storage_path.exists()
    assert result.parsed_document is not None
    assert {block.block_type for block in result.blocks} >= {"heading", "paragraph", "table", "code"}
    assert all(block.block_id for block in result.blocks)
    assert any(block.line_start == 3 and block.line_end == 3 for block in result.blocks)
    assert any(block.block_type == "code" and block.line_start == 9 for block in result.blocks)


def test_same_content_has_stable_hash_and_block_ids(tmp_path: Path):
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("# Same\n\ncontent\n", encoding="utf-8")
    second.write_text("# Same\n\ncontent\n", encoding="utf-8")

    inventory = AssetInventory(tmp_path / "data")
    left = inventory.inspect(first)
    right = inventory.inspect(second)

    assert left.sha256 == right.sha256
    assert [b.block_id for b in left.blocks] == [b.block_id for b in right.blocks]
    assert left.storage_path == right.storage_path


def test_empty_file_is_failed_without_parser_exception(tmp_path: Path):
    source = tmp_path / "empty.md"
    source.write_bytes(b"")

    result = AssetInventory(tmp_path / "data").inspect(source)

    assert result.status is ParseStatus.FAILED
    assert result.error_code == "empty_file"
    assert result.blocks == ()


def test_unsupported_extension_is_failed(tmp_path: Path):
    source = tmp_path / "paper.exe"
    source.write_bytes(b"not a paper")

    result = AssetInventory(tmp_path / "data").inspect(source)

    assert result.status is ParseStatus.FAILED
    assert result.error_code == "unsupported_type"


def test_pdf_parser_keeps_page_location_when_dependency_is_available(tmp_path: Path):
    fitz = pytest.importorskip("fitz")
    source = tmp_path / "paper.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Evidence on page one")
    document.save(source)
    document.close()

    result = AssetInventory(tmp_path / "data").inspect(source)

    assert result.status is ParseStatus.PARSED
    assert any(block.page == 1 for block in result.blocks)


def test_docx_parser_keeps_paragraph_and_table_location_when_dependency_available(tmp_path: Path):
    docx = pytest.importorskip("docx")
    source = tmp_path / "paper.docx"
    document = docx.Document()
    document.add_paragraph("Problem statement")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "x"
    table.cell(0, 1).text = "y"
    table.cell(1, 0).text = "1"
    table.cell(1, 1).text = "2"
    document.save(source)

    result = AssetInventory(tmp_path / "data").inspect(source)

    assert result.status is ParseStatus.PARSED
    assert any(block.block_type == "paragraph" for block in result.blocks)
    assert any(block.block_type == "table" for block in result.blocks)
