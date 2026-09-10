"""
检索模块：关键词 + 向量混合检索
"""
from app.rag.embedder import get_embedding
from app.rag.store import get_collection


def vector_search(query: str, top_k: int = 5) -> list:
    """向量检索：语义相似"""
    collection = get_collection()
    if collection.count() == 0:
        return []
    
    query_embedding = get_embedding(query)
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    
    return _format_results(results)


def keyword_search(query: str, top_k: int = 5) -> list:
    """关键词检索：按内容匹配"""
    collection = get_collection()
    if collection.count() == 0:
        return []
    
    results = collection.get(
        where_document={"$contains": query}
    )
    
    items = []
    ids = results.get("ids", [])
    docs = results.get("documents", [])
    metas = results.get("metadatas", [])
    
    for i in range(len(ids)):
        items.append({
            "id": ids[i],
            "content": docs[i],
            "metadata": metas[i],
            "score": 1.0,
            "source": "keyword"
        })
    
    return items[:top_k]


def hybrid_search(query: str, top_k: int = 5) -> list:
    """混合检索：关键词 + 向量，按排名融合"""
    # 1. 关键词检索
    kw_results = keyword_search(query, top_k=top_k)
    kw_ids = {r["id"] for r in kw_results}
    
    # 2. 向量检索
    vec_results = vector_search(query, top_k=top_k * 2)
    
    # 3. 融合：按排名给分（第1名1.0，第2名0.9...）
    merged = {}
    
    for rank, r in enumerate(vec_results):
        rid = r["id"]
        # 按排名打分：第1名1.0，第2名0.9，以此类推，最低0.1
        score = max(1.0 - rank * 0.1, 0.1)
        # 关键词命中的加权
        if rid in kw_ids:
            score += 0.3
        merged[rid] = {**r, "score": round(score, 3)}
    
    # 关键词独有的也加进来
    for r in kw_results:
        if r["id"] not in merged:
            merged[r["id"]] = {**r, "score": 0.5}
    
    result_list = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    
    return result_list[:top_k]


def _format_results(results: dict) -> list:
    """格式化 Chroma 返回结果"""
    items = []
    
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0] if results.get("distances") else [0] * len(ids)
    
    for i in range(len(ids)):
        distance = distances[i] if i < len(distances) else 0
        try:
            distance = float(distance)
        except (TypeError, ValueError):
            distance = 0
        
        # cosine 距离范围是 0-2，转换：相似度 = 1 - distance/2
        score = max(1.0 - distance / 2.0, 0.0)
        
        items.append({
            "id": ids[i],
            "content": docs[i],
            "metadata": metas[i],
            "score": round(score, 4),
            "source": "vector"
        })
    
    return items


def format_context(items: list) -> str:
    """把检索结果拼成给大模型的上下文"""
    if not items:
        return "（无相关资料）"
    
    lines = []
    for i, item in enumerate(items, 1):
        meta = item.get("metadata", {})
        lines.append(
            f"【资料{i}】[{meta.get('type', '')}] {meta.get('name', '')}\n{item['content']}"
        )
    
    return "\n\n".join(lines)