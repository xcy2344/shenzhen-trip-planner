"""
向量化模块：把文本转成向量
用百炼的 text-embedding-v1 模型
"""
import dashscope
from app.core.config import config


# 百炼 Embedding 模型
EMBEDDING_MODEL = "text-embedding-v1"

# DashScope 单次最多处理 25 条
BATCH_SIZE = 25


def get_embedding(text: str) -> list:
    """把单条文本转向量"""
    dashscope.api_key = config.BAILIAN_API_KEY
    
    response = dashscope.TextEmbedding.call(
        model=EMBEDDING_MODEL,
        input=text
    )
    
    if response.status_code != 200:
        raise RuntimeError(f"Embedding 失败：{response.message}")
    
    return response["output"]["embeddings"][0]["embedding"]


def get_embeddings(texts: list) -> list:
    """批量转向量（自动分批）"""
    dashscope.api_key = config.BAILIAN_API_KEY
    
    all_embeddings = []
    
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        
        response = dashscope.TextEmbedding.call(
            model=EMBEDDING_MODEL,
            input=batch
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Embedding 失败：{response.message}")
        
        # 按顺序取出向量
        batch_embeddings = [
            item["embedding"] for item in response["output"]["embeddings"]
        ]
        all_embeddings.extend(batch_embeddings)
    
    return all_embeddings