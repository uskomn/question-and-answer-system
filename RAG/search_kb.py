"""
search_kb.py  ——  本地电脑检索脚本
====================================
从服务器拉取 kb_data/ 后，在本地电脑上运行此脚本进行语义检索。
只需 CPU，加载 Embedding 模型对 query 编码，FAISS 完成向量搜索。

依赖安装（本地）：
    pip install faiss-cpu sentence-transformers numpy

用法：
    # 交互模式
    python search_kb.py

    # 单次查询
    python search_kb.py --query "深度学习和神经网络的关系是什么？"

    # 返回 3 条，以 LLM prompt 格式输出
    python search_kb.py --query "四大发明" --top-k 3 --llm-context

    # 指定知识库路径
    python search_kb.py --kb-dir ~/kb_data --query "量子纠缠"
"""

import argparse
import json
import time
from pathlib import Path

import faiss
import numpy as np


class KnowledgeBase:
    def __init__(self, kb_dir: str = "./kb_data"):
        self.kb_dir = Path(kb_dir)
        self._verify_files()

        print(f"\n加载知识库: {self.kb_dir.resolve()}")
        t0 = time.time()

        # 1. 读取模型信息
        with open(self.kb_dir / "model_info.json", encoding="utf-8") as f:
            info = json.load(f)
        # 本地
        # self.model_name: str = "E:\PycharmProjects\question and answer system\RAG\models/bge-base-zh-v1.5"
        #服务器
        self.model_name: str = "/home/ubuntu/question-and-answer-system/RAG/models/bge-base-zh-v1.5"
        self.dim: int               = info["dim"]
        self.query_instruction: str = info.get("query_instruction", "")

        # 2. 加载 Embedding 模型（只用于 query 编码，CPU 足够）
        print(f"  Embedding 模型: {self.model_name}")
        self._load_model()

        # 3. 加载 FAISS 索引
        self.index = faiss.read_index(str(self.kb_dir / "faiss.index"))
        print(f" FAISS 索引  "
              f"维度={self.index.d}  向量数={self.index.ntotal:,}")

        # 4. 加载文本块
        with open(self.kb_dir / "chunks.jsonl", encoding="utf-8") as f:
            self.chunks: list[dict] = [json.loads(line) for line in f]
        print(f"文本块: {len(self.chunks):,} 块")

        # 5. 构建信息
        cfg_path = self.kb_dir / "build_config.json"
        if cfg_path.exists():
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            print(f"  🗓 构建于 {cfg.get('build_date', '?')}  "
                  f"文章块={cfg.get('chunk_count', '?'):,}  "
                  f"索引={cfg.get('index_type', '?')}")

        print(f"  ⏱ 加载耗时 {time.time()-t0:.2f}s\n")

    def _verify_files(self):
        required = ["faiss.index", "chunks.jsonl", "model_info.json"]
        missing = [f for f in required if not (self.kb_dir / f).exists()]
        if missing:
            raise FileNotFoundError(
                f"知识库文件缺失: {missing}\n"
                f"请先从服务器拉取 kb_data/ 目录，或运行 build_kb.py 构建。\n"
                f"拉取命令示例:\n"
                f"  scp user@server:/path/to/kb_data.tar.gz ./\n"
                f"  tar -xzf kb_data.tar.gz"
            )

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "请安装: pip install sentence-transformers"
            )
        # 本地检索只用 CPU，query 编码量很小
        self._st = SentenceTransformer(self.model_name, device="cpu")

    def _encode_query(self, query: str) -> np.ndarray:
        """编码 query，BGE 系列自动加前缀，返回 (1, dim) float32。"""
        text = self.query_instruction + query if self.query_instruction else query
        vec = self._st.encode(
            [text],
            batch_size=1,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vec.astype(np.float32)

    # ──────────────────────────────────────────────────────────────────────────
    # 检索接口
    # ──────────────────────────────────────────────────────────────────────────

    def search(self, question: str, top_k: int = 5) -> tuple[list[dict], float]:
        """
        语义检索，返回最相关的 top_k 个文本块。

        返回：
            results:    [{"chunk_id", "title", "text", "score"}, ...]
            elapsed_ms: 检索耗时（毫秒）
        """
        t0 = time.time()
        q_vec = self._encode_query(question)
        scores, indices = self.index.search(q_vec, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            chunk = self.chunks[idx]
            results.append({
                "chunk_id": int(idx),
                "title":    chunk["title"],
                "text":     chunk["text"],
                "score":    float(score),
            })
        return results, (time.time() - t0) * 1000

    def search_diverse(self, question: str,
                       top_k: int = 5) -> tuple[list[dict], float]:
        """
        去重检索：每篇文章只保留得分最高的一个片段，结果来源更多样。
        RAG 场景推荐。
        """
        raw, ms = self.search(question, top_k=top_k * 4)
        seen: set[str] = set()
        results = []
        for r in raw:
            if r["title"] not in seen:
                seen.add(r["title"])
                results.append(r)
            if len(results) >= top_k:
                break
        return results, ms


def print_results(question: str, results: list[dict],
                  elapsed_ms: float, max_len: int = 500):
    bar = "=" * 65
    print(f"\n{bar}")
    print(f"问题：{question}")
    print(f"   耗时：{elapsed_ms:.1f} ms  |  返回 {len(results)} 条")
    print(bar)
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] 《{r['title']}》  "
              f"相似度={r['score']:.4f}  chunk_id={r['chunk_id']}")
        print("─" * 55)
        text = r["text"][:max_len] + ("..." if len(r["text"]) > max_len else "")
        print(text)
    print()

