from app.rag.retriever import hybrid_search, format_context

# 测试 3 个查询
queries = [
    "深圳有什么山可以爬",
    "哪里能吃海鲜",
    "晚上看日落的好去处"
]

for q in queries:
    print(f"\n{'='*60}")
    print(f"查询：{q}")
    print('='*60)
    
    results = hybrid_search(q, top_k=3)
    
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        print(f"{i}. [{meta.get('type')}] {meta.get('name')} (分数: {r['score']})")
        print(f"   {r['content'][:60]}...")
    
    print("\n--- 格式化上下文 ---")
    print(format_context(results)[:300])