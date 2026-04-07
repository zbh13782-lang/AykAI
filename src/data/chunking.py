import re
import uuid
from typing import Any

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from src.indexing.schema import ChildChunk, ParentChunk



def _detect_chunk_mode(source: str, metadata: dict[str, Any]) -> str:
    """检查格式"""
    normalized_source = (source or "").lower()
    mime_type = str(metadata.get("mime_type", "")).lower()
    file_type = str(metadata.get("file_type", "")).lower()

    if normalized_source.endswith((".md", ".markdown")) or mime_type == "text/markdown" or file_type == "markdown":
        return "markdown"
    if normalized_source.endswith(".pdf") or mime_type == "application/pdf" or file_type == "pdf":
        return "pdf"
    return "text"

def _split_markdown_parent_blocks(content:str, parent_chunk_size:int, parent_overlap:int) -> list[dict[str, Any]]:

    #标题分
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        strip_headers=False,
    )

    docs = header_splitter.split_text(content)
    sections = docs if docs else []

    #没有标题，就按整篇继续走
    if not sections:
        class _Doc:
            page_content = content
            metadata : dict[str, Any]  = {}
        sections = [_Doc()]

    parent_blocks:list[dict[str, Any]] = []
    default_splitter = RecursiveCharacterTextSplitter(
        chunk_size=parent_chunk_size,
        chunk_overlap=parent_overlap,
        separators=["\n\n", "\n", "。", ".", " ", ""],
    )
    code_splitter = RecursiveCharacterTextSplitter(
        chunk_size=parent_chunk_size,
        chunk_overlap=min(30, parent_overlap),
        separators=["\n", " ", ""],
    )

    for section in sections:
        # 提取元数据  构建标题路径
        meta = dict(getattr(section, "metadata", {}) or {})
        heading_path = " > ".join([str(meta.get(k)).strip() for k in ("h1", "h2", "h3") if str(meta.get(k, "")).strip()])
        section_blocks = _split_markdown_semantic_blocks(section.page_content)
        if not section_blocks:
            section_blocks = [(section.page_content, "paragraph")]

        for block_text,block_type in section_blocks:
            splitter = code_splitter if block_type in {"code","table"} else default_splitter
            chunks = splitter.split_text(block_text)
            for chunk in chunks:
                cleaned = chunk.strip()
                if not cleaned:
                    continue
                if len(cleaned) < 20 and len(chunks) > 1:
                    continue
                block_meta = {
                    **meta,
                    "content_type" : block_type,
                    "heading_path" : heading_path,
                }
                parent_blocks.append({"content": cleaned, "metadata": block_meta})

    return parent_blocks

def _split_markdown_semantic_blocks(section : str) -> list[tuple[str, str]]:
    lines = section.splitlines()
    blocks:list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        #代码块处理
        if stripped.startswith("```"):
            code_lines = [line]
            i += 1
            while i < len(lines):
                code_lines.append(lines[i])
                if lines[i].strip().startswith("```"):
                    i += 1
                    break
                i += 1
            blocks.append(("\n".join(code_lines).strip(),'code'))
            continue
        #表格处理
        if "|" in line:
            table_lines = [line]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                nex_stripped = nxt.strip()
                if not nex_stripped:
                    break
                if '|' not in nxt:
                    break
                table_lines.append(nxt)
                i += 1
            if len(table_lines) >= 2:
                blocks.append(("\n".join(table_lines).strip(), "table"))
                continue

        if stripped.startswith(("- ", "* ", "+ ")) or re.match(r"^\d+\.\s", stripped):
            list_lines = [line]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                nxt_stripped = nxt.strip()
                if not nxt_stripped:
                    break
                if nxt_stripped.startswith(("- ", "* ", "+ ")) or re.match(r"^\d+\.\s", nxt_stripped):
                    list_lines.append(nxt_stripped)
                    i += 1
                    continue
                break
            blocks.append(("\n".join(list_lines).strip(), "list"))
            continue

        para_lines = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            nxt_stripped = nxt.strip()
            if not nxt_stripped:
                break
            if nxt_stripped.startswith("```"):
                break
            if "|" in nxt and len(para_lines) == 1:
                break
            if nxt_stripped.startswith(("- ", "* ", "+ ")) or re.match(r"^\d+\.\s", nxt_stripped):
                break
            para_lines.append(nxt)
            i += 1
        blocks.append(("\n".join(para_lines).strip(), "paragraph"))

    return [(text, block_type) for text, block_type in blocks if text]

def _split_pdf_parent_texts(content: str, parent_chunk_size: int, parent_overlap: int) -> list[str]:
    """未考虑图片！！！"""

    pages = [p.strip() for p in content.split("\f") if p.strip()]
    if not pages:
        pages = [content]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=parent_chunk_size,
        chunk_overlap=parent_overlap,
        separators=["\n\n", "\n", ". ", "。", " ", ""],
    )

    parent_texts: list[str] = []
    for i, page in enumerate(pages, start=1):
        chunks = splitter.split_text(page)
        parent_texts.extend([f"[page {i}] {c}" for c in chunks if c.strip()])
    return parent_texts

def build_parent_child_chunks(
        doc_id:str,
        source:str,
        content:str,
        metadata:dict[str, Any] | None = None,
        parent_chunk_size: int  = 1600,
        parent_overlap:int = 120,
        child_chunk_size: int = 400,
        child_overlap: int = 60,
) -> tuple[list[ParentChunk], list[ChildChunk]]:
    metadata = metadata or {}
    mode = _detect_chunk_mode(source=source, metadata=metadata)
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_chunk_size,
        chunk_overlap=child_overlap,
        separators=["\n\n", "\n", "。", ".", " ", ""],
    )

    if mode == "markdown":
        parent_blocks = _split_markdown_parent_blocks(content, parent_chunk_size, parent_overlap)
    elif mode == "pdf":
        parent_blocks = [{"content": t, "metadata": {}} for t in
                         _split_pdf_parent_texts(content, parent_chunk_size, parent_overlap)]
    else:
        parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_chunk_size,
            chunk_overlap=parent_overlap,
            separators=["\n\n", "\n", "。", ".", " ", ""],
        )
        parent_blocks = [{"content": t, "metadata": {}} for t in parent_splitter.split_text(content)]

    parents: list[ParentChunk] = []
    children: list[ChildChunk] = []

    for parent_idx, block in enumerate(parent_blocks):
        ptxt = block["content"]
        block_metadata = {**metadata, **(block.get("metadata") or {})}
        parent_id = f"p-{uuid.uuid4().hex}"
        child_texts = child_splitter.split_text(ptxt)
        child_ids: list[str] = []

        for child_idx, ctxt in enumerate(child_texts):
            chunk_id = f"{doc_id}-c-{parent_idx}-{child_idx}-{uuid.uuid4().hex[:8]}"
            child_ids.append(chunk_id)
            children.append(
                ChildChunk(
                    chunk_id=chunk_id,
                    parent_id=parent_id,
                    doc_id=doc_id,
                    content=ctxt,
                    source=source,
                    chunk_order=child_idx,
                    metadata=block_metadata,
                )
            )

        parents.append(
            ParentChunk(
                parent_id=parent_id,
                doc_id=doc_id,
                content=ptxt,
                source=source,
                child_ids=child_ids,
                metadata=block_metadata,
            )
        )

    return parents, children
