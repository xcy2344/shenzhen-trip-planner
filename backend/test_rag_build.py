from app.rag.store import build_index

count = build_index(force_rebuild=True)
print(f"索引构建完成，共 {count} 条")