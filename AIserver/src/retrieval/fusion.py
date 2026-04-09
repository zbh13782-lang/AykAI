from __future__ import annotations

'''两种检索策略混合'''

def rrf_fusion(
        vector_rows: list[dict],
        bm25_rows: list[dict],
        vector_weight: float,
        bm25_weight: float,
        rrf_k: int = 60,
        dedup_by: str = "parent_id",
        threshold: float = 0.0,
        top_k: int = 8,
) -> list[dict]:
    fused : dict[str,dict] = {}
    '''得分相同，优先取向量结果'''
    source_priority = {"vector" : 0,"bm25" : 1}

    def _maybe_update_rep(existing: dict, row: dict, rank: int, source: str) -> None:
        best_rank = int(existing.get("_best_rank", 10**9))
        best_source = str(existing.get("_best_source", "bm25"))
        should_update = rank < best_rank or (
            rank == best_rank and source_priority.get(source, 99) < source_priority.get(best_source, 99)
        )
        if should_update:
            existing.update({k: v for k, v in row.items() if k != "score"})
            existing["_best_rank"] = rank
            existing["_best_source"] = source

    for rank, row in enumerate(vector_rows, start=1):
        key = row.get(dedup_by) or row["chunk_id"]
        rrf_score = 1.0 / float(rrf_k + rank)
        existing = fused.get(key)
        if existing is None:
            fused[key] = {
                **row,
                "_vector_rrf": rrf_score,
                "_bm25_rrf": 0.0,
                "_best_rank": rank,
                "_best_source": "vector",
            }
        else:
            existing["_vector_rrf"] += rrf_score
            _maybe_update_rep(existing, row, rank=rank, source="vector")

    for rank, row in enumerate(bm25_rows, start=1):
        key = row.get(dedup_by) or row["chunk_id"]
        rrf_score = 1.0 / float(rrf_k + rank)
        existing = fused.get(key)
        if existing is None:
            fused[key] = {
                **row,
                "_vector_rrf": 0.0,
                "_bm25_rrf": rrf_score,
                "_best_rank": rank,
                "_best_source": "bm25",
            }
        else:
            existing["_bm25_rrf"] += rrf_score
            _maybe_update_rep(existing, row, rank=rank, source="bm25")

    ranked_candidates: list[dict] = []
    for row in fused.values():
        final_score = vector_weight * float(row.get("_vector_rrf", 0.0)) + bm25_weight * float(row.get("_bm25_rrf", 0.0))
        if final_score < threshold:
            continue
        row["score"] = final_score
        row.pop("_vector_rrf", None)
        row.pop("_bm25_rrf", None)
        row.pop("_best_rank", None)
        row.pop("_best_source", None)
        ranked_candidates.append(row)

    ranked = sorted(ranked_candidates, key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]
