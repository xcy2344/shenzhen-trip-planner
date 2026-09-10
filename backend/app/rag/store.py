"""
向量存储模块：把知识库存入 Chroma
使用 cosine 距离
"""
import chromadb
from pathlib import Path
from app.rag.knowledge import KNOWLEDGE_BASE
from app.rag.embedder import get_embeddings


CHROMA_PATH = Path(__file__).parent.parent.parent / "chroma_data"
COLLECTION_NAME = "shenzhen_travel"

_client = None
_collection = None


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return _client


def get_collection():
    global _collection
    if _collection is None:
        client = get_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={
                "description": "深圳旅游知识库",
                "hnsw:space": "cosine"   # 关键：用 cosine 距离
            }
        )
    return _collection


def build_index(force_rebuild: bool = False):
    """构建向量索引"""
    collection = get_collection()
    
    if not force_rebuild and collection.count() > 0:
        print(f"索引已存在，共 {collection.count()} 条")
        return collection.count()
    
    if force_rebuild:
        client = get_client()
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        global _collection
        _collection = None
        collection = get_collection()
    
    ids = [item["id"] for item in KNOWLEDGE_BASE]
    documents = [item["content"] for item in KNOWLEDGE_BASE]
    metadatas = [
        {"type": item["type"], "name": item["name"]}
        for item in KNOWLEDGE_BASE
    ]
    
    print(f"正在向量化 {len(documents)} 条数据...")
    embeddings = get_embeddings(documents)
    
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )
    
    print(f"✅ 已存入 {collection.count()} 条数据")
    return collection.count()