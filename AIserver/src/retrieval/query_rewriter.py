from __future__ import annotations

import json
import re
from typing import Any

def _build_rewrite_prompt(query: str) -> str:
    return (
        "你是检索优化助手。请将用户问题改写为更适合检索召回的表达，并输出严格 JSON。\n"
        "不要输出任何 JSON 以外文本。\n"
        "JSON schema:\n"
        '{"query_understanding": "string", "rewrite_strategy": "identity|expand_simple|simplify_and_decompose", '
        '"optimized_query": "string", "variants": ["string"], "subtasks": ["string"]}\n\n'
        f"用户问题:\n{query}\n\n"
        "要求:\n"
        "1) 简短问题请扩展为更可检索的表达，比如问题不明确，用户只输入 “鱼” ， 你可以拓展为相关鱼相关食材，菜名，技巧 \n"
        "2) 复杂长问题请简化并拆解为子任务；\n"
        "3) 如果问题有错别字，请修正拼写错误，比如 “不知道” 写成“布吉岛” "
        "4) 如果用户问题表达不规范，比如 “咋搞这玩意” 你可以拓展为“这个任务怎么做？” "
    )


def _normalize_text(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").strip())


def _split_to_subtasks(query: str) -> list[str]:
    parts = [
        p.strip(" ，。；;!！?？")
        for p in re.split(r"[\n；;。!?！？]+", query)
        if p.strip(" ，。；;!！?？")
    ]
    return [p for p in parts if p]


def _empty_result() -> dict[str, Any]:
    return {
        "query_understanding": "empty",
        "rewrite_strategy": "identity",
        "optimized_query": "",
        "variants": [],
        "subtasks": [],
    }


def _dedupe_variants(variants: list[str]) -> list[str]:
    return list(dict.fromkeys(v.strip() for v in variants if v and v.strip()))


def _rule_based_rewrite(normalized: str) -> dict[str, Any]:
    if not normalized:
        return _empty_result()

    char_len = len(normalized)
    word_len = len(normalized.split())
    variants = [normalized]
    subtasks: list[str] = []
    understanding = normalized
    strategy = "identity"

    has_multiple_clauses = len(re.findall(r"[，,；;。]", normalized)) >= 2
    if char_len >= 40 or has_multiple_clauses:
        strategy = "simplify_and_decompose"
        subtasks = _split_to_subtasks(normalized)
        if len(subtasks) >= 2:
            concise = "；".join(subtasks[:3])
            understanding = f"这是一个复合问题，关键任务：{concise}"
            variants.extend(subtasks[:3])
        else:
            concise = normalized[:120]
            understanding = f"这是一个较长问题，可简化为：{concise}"
            variants.append(f"请给出 {concise} 的分步执行方案")
    elif char_len <= 12 or word_len <= 4:
        strategy = "expand_simple"
        understanding = f"用户想解决的核心问题是：{normalized}"
        variants.extend(
            [
                f"{normalized} 的实现步骤",
                f"{normalized} 的最佳实践与注意事项",
                f"如何落地 {normalized}（含技术方案与执行顺序）",
            ]
        )

    deduped = _dedupe_variants(variants)
    optimized_query = deduped[0]
    if strategy == "expand_simple" and len(deduped) > 1:
        optimized_query = deduped[1]

    return {
        "query_understanding": understanding,
        "rewrite_strategy": strategy,
        "optimized_query": optimized_query,
        "variants": deduped,
        "subtasks": subtasks,
    }


def _parse_json_block(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _llm_rewrite(chat_model, normalized: str) -> dict[str, Any] | None:
    prompt = _build_rewrite_prompt(normalized)
    content = getattr(chat_model.invoke(prompt), "content", "")
    parsed = _parse_json_block(content if isinstance(content, str) else str(content))
    if not parsed:
        return None

    variants = _dedupe_variants(list(parsed.get("variants") or []))
    if normalized not in variants:
        variants.insert(0, normalized)
    optimized_query = str(parsed.get("optimized_query") or "").strip()
    if not optimized_query:
        optimized_query = variants[0] if variants else normalized
    if optimized_query not in variants:
        variants.insert(0, optimized_query)

    return {
        "query_understanding": str(parsed.get("query_understanding") or normalized),
        "rewrite_strategy": str(parsed.get("rewrite_strategy") or "identity"),
        "optimized_query": optimized_query,
        "variants": variants,
        "subtasks": [str(x).strip() for x in (parsed.get("subtasks") or []) if str(x).strip()],
    }


def rewrite_query(query: str, chat_model=None) -> dict[str, Any]:
    normalized = _normalize_text(query)
    if not normalized:
        return _empty_result()

    if chat_model is not None:
        try:
            llm_result = _llm_rewrite(chat_model, normalized)
            if llm_result is not None:
                return llm_result
        except Exception:  # noqa: BLE001
            pass

    return _rule_based_rewrite(normalized)
