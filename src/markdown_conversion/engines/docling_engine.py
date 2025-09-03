from typing import Any, Dict, Tuple


def try_import() -> Any:
    try:
        from docling.document_converter import DocumentConverter
        return DocumentConverter
    except Exception:
        return None


def convert(pdf_path: str) -> Tuple[str, Dict[str, Any]]:
    DocumentConverter = try_import()
    if DocumentConverter is None:
        return "", {"engine": "docling", "status": "unavailable"}
    try:
        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        md_text = ""
        if hasattr(result, "document") and result.document is not None:
            doc = result.document
            if hasattr(doc, "export_to_markdown"):
                md_text = doc.export_to_markdown()  # type: ignore
            elif hasattr(doc, "to_markdown"):
                md_text = doc.to_markdown()  # type: ignore
            elif hasattr(result, "export_markdown"):
                md_text = result.export_markdown()  # type: ignore
        meta = {"engine": "docling", "status": "ok" if md_text else "empty"}
        return md_text, meta
    except Exception as e:
        return "", {"engine": "docling", "status": f"error: {e}"}


