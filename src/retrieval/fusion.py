from __future__ import annotations

'''两种检索策略混合'''

def _normalize_scores(rows : list[dict]) -> list[dict]:
    '''分数归一化'''
    if not rows:
        return rows
    max_score = max(r['score'] for r in rows)
    if max_score <= 0:
        return [{**r, "norm_score": 0.0} for r in rows]
    return [{**r, "norm_score": float(r["score"]) / float(max_score)} for r in rows]

def weighted_fusion(
        vector_rows:list[dict],
        bm25_rows:list[dict],
        vector_weight:float,
        bm25_weight:float,
        dedup_by:str = "parent_id",#去重字段
        threshold:float = 0.0,#分数阈值
        top_k:int = 8
) -> list[dict]:
    fused : dict[str,dict] = {}

    for row in _normalize_scores(vector_rows):
        key = row.get(dedup_by) or row["chunk_id"]
        score = row["norm_score"] * vector_weight
        existing = fused.get(key)
        if existing is None:
            #不存在，添加
            fused[key] = {**row, "norm_score": score}
        else:
            #存在，加分
            existing["score"] += score
            if row["norm_score"] > existing.get("norm_score", 0):
                existing.update({k: v for k, v in row.items() if k != "score"})

    for row in _normalize_scores(bm25_rows):
        key = row.get(dedup_by) or row["chunk_id"]
        score = row["norm_score"] * bm25_weight
        existing = fused.get(key)
        if existing is None:
            fused[key] = {**row, "score": score}
        else:
            existing["score"] += score
            if row["norm_score"] > existing.get("norm_score", 0):
                existing.update({k: v for k, v in row.items() if k != "score"})

    ranked = sorted((r for r in fused.values() if r["score"] >= threshold), key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]