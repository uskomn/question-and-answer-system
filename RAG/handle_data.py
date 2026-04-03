"""
build_kb.py  ——  GPU 加速版 Embedding + FAISS 中文维基百科知识库构建器
========================================================================
专为算力服务器设计：
  • 自动检测全部 GPU，多卡并行 Embedding 编码
  • AMP float16 半精度推理（显存减半、速度提升约 1.5-2x）
  • 向量分片落盘（shard_*.npy），支持断点续传
  • 构建完成后自动打包 kb_data.tar.gz，方便拉取到本地

流程：
  XML bz2 流式解析 → Wikitext 清洗 → 切块(512字)
    → GPU Embedding 批量编码（多卡并行）
    → 向量分片保存到 kb_data/shards/
    → 合并分片 → FAISS IndexFlatIP 建索引
    → 持久化 → 打包

服务器依赖安装：
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    pip install sentence-transformers faiss-gpu tqdm numpy

推荐 Embedding 模型（中文 MTEB 榜单）：
    BAAI/bge-small-zh-v1.5   dim=512   33M   最快
    BAAI/bge-base-zh-v1.5    dim=768   102M  均衡  ← 默认
    BAAI/bge-large-zh-v1.5   dim=1024  326M  最强

用法：
    # 全量构建（自动使用所有 GPU）
    python build_kb.py --input zhwiki-20251220-pages-articles-multistream.xml.bz2

    # 调试：只处理 5 万篇
    python build_kb.py --input zhwiki-*.xml.bz2 --max-articles 50000

    # 指定模型 + 构建后打包
    python build_kb.py --input zhwiki-*.xml.bz2 \\
        --model BAAI/bge-large-zh-v1.5 --pack

    # 超过 500 万文本块时用近似索引
    python build_kb.py --input zhwiki-*.xml.bz2 --use-ivf
"""

import argparse
import bz2
import gc
import json
import logging
import os
import re
import sys
import tarfile
import time
from pathlib import Path

import faiss
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# 1. GPU 环境检测
# ──────────────────────────────────────────────────────────────────────────────

def detect_gpus() -> dict:
    info = {"available": False, "count": 0, "names": [], "total_vram_gb": 0.0}
    try:
        import torch
        if not torch.cuda.is_available():
            return info
        info["available"] = True
        info["count"] = torch.cuda.device_count()
        for i in range(info["count"]):
            name = torch.cuda.get_device_name(i)
            vram = torch.cuda.get_device_properties(i).total_memory / 1024 ** 3
            info["names"].append(f"  GPU{i}: {name}  ({vram:.1f} GB)")
            info["total_vram_gb"] += vram
    except ImportError:
        pass
    return info


def auto_batch_size(total_vram_gb: float, dim: int) -> int:
    """根据总显存推荐 encode batch size（保守取 40% 显存）。"""
    safe = total_vram_gb * 0.40 * 1024 ** 3
    bytes_per_sample = dim * 2 * 64        # fp16，保守系数
    raw = int(safe / bytes_per_sample)
    # 取 2 的幂次，范围 [128, 2048]
    raw = max(128, min(2048, raw))
    return 2 ** int(np.log2(raw))


# ──────────────────────────────────────────────────────────────────────────────
# 2. XML 流式解析
# ──────────────────────────────────────────────────────────────────────────────
# multistream bz2 格式无法用 iterparse 处理，改用逐行读取（与参考实现一致）

SKIP_TITLE_PREFIXES = (
    "Wikipedia:", "维基百科:", "Help:", "帮助:",
    "Template:", "模板:", "Category:", "分类:",
    "Portal:", "专题:", "Talk:", "讨论:",
    "File:", "文件:", "Image:", "图像:",
    "Module:", "模块:", "MediaWiki:", "User:", "用户:",
)

# 匹配 <title>...</title>（同一行内）
_RE_TITLE    = re.compile(r"<title>(.*?)</title>")
# 匹配 <ns>...</ns>
_RE_NS       = re.compile(r"<ns>(\d+)</ns>")
# 匹配 <text ...>content</text>（整段在同一行）
_RE_TEXT_ONE = re.compile(r"<text[^>]*>(.*?)</text>", re.DOTALL)
# 匹配多行 <text> 开头
_RE_TEXT_BGN = re.compile(r"<text[^>]*>(.*)")


def iter_wiki_articles(bz2_path: str, max_articles: int | None = None):
    """
    逐行读取 bz2 XML，yield (title, wikitext)。
    兼容 multistream 格式，只返回主命名空间（ns=0）非重定向条目。
    """
    count   = 0
    title   = None
    ns_val  = None
    in_text = False
    buf: list[str] = []

    with bz2.open(bz2_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            # ── 页面开始，重置状态 ──────────────────────────────────────────
            if "<page>" in line:
                title  = None
                ns_val = None
                in_text = False
                buf     = []
                continue

            # ── 标题 ────────────────────────────────────────────────────────
            if "<title>" in line:
                m = _RE_TITLE.search(line)
                if m:
                    title = m.group(1)
                continue

            # ── 命名空间 ─────────────────────────────────────────────────────
            if "<ns>" in line:
                m = _RE_NS.search(line)
                if m:
                    ns_val = m.group(1)
                continue

            # ── 文本段 ───────────────────────────────────────────────────────
            if "<text" in line and not in_text:
                # 情况 A：<text ...>content</text> 同一行
                m = _RE_TEXT_ONE.search(line)
                if m:
                    wikitext = m.group(1)
                    # 过滤：非主命名空间 / 特殊标题 / 重定向
                    if (ns_val == "0"
                            and title
                            and not any(title.startswith(p) for p in SKIP_TITLE_PREFIXES)
                            and not wikitext.strip().lower().startswith("#redirect")
                            and not wikitext.strip().startswith("#重定向")):
                        yield title, wikitext
                        count += 1
                        if max_articles and count >= max_articles:
                            return
                else:
                    # 情况 B：<text ...>开头，内容跨多行
                    m2 = _RE_TEXT_BGN.search(line)
                    buf = [m2.group(1)] if m2 else []
                    in_text = True
                continue

            if in_text:
                if "</text>" in line:
                    buf.append(line[:line.index("</text>")])
                    wikitext = "".join(buf)
                    in_text = False
                    buf = []
                    if (ns_val == "0"
                            and title
                            and not any(title.startswith(p) for p in SKIP_TITLE_PREFIXES)
                            and not wikitext.strip().lower().startswith("#redirect")
                            and not wikitext.strip().startswith("#重定向")):
                        yield title, wikitext
                        count += 1
                        if max_articles and count >= max_articles:
                            return
                else:
                    buf.append(line)


# ──────────────────────────────────────────────────────────────────────────────
# 3. Wikitext 清洗
# ──────────────────────────────────────────────────────────────────────────────

_RE_TEMPLATE  = re.compile(r"\{\{[^{}]*?\}\}", re.DOTALL)
_RE_LINK_FILE = re.compile(r"\[\[(?:File|Image|文件|图像|图片):[^\]]*?\]\]", re.I)
_RE_LINK_CAT  = re.compile(r"\[\[(?:Category|分类):[^\]]*?\]\]", re.I)
_RE_WIKILINK  = re.compile(r"\[\[(?:[^|\]]*?\|)?([^\]]*?)\]\]")
_RE_EXT_LINK  = re.compile(r"\[https?://\S+\s*([^\]]*?)\]")
_RE_HEADING   = re.compile(r"={2,6}(.+?)={2,6}")
_RE_HTML      = re.compile(r"<[^>]+>")
_RE_ENT       = re.compile(r"&[a-zA-Z]+;|&#\d+;")
_RE_SPACES    = re.compile(r"[^\S\n]{2,}")
_RE_NEWLINES  = re.compile(r"\n{3,}")


def clean_wikitext(text: str) -> str:
    for _ in range(6):
        new = _RE_TEMPLATE.sub("", text)
        if new == text:
            break
        text = new
    text = _RE_LINK_FILE.sub("", text)
    text = _RE_LINK_CAT.sub("", text)
    text = _RE_WIKILINK.sub(r"\1", text)
    text = _RE_EXT_LINK.sub(r"\1", text)
    text = _RE_HEADING.sub(r"\1", text)
    text = _RE_HTML.sub("", text)
    text = _RE_ENT.sub("", text)
    lines = [l for l in text.splitlines()
             if not l.strip().startswith("|") and not l.strip().startswith("!")]
    text = "\n".join(lines)
    text = text.replace("'''", "").replace("''", "")
    text = text.replace("__NOTOC__", "").replace("__TOC__", "")
    text = _RE_SPACES.sub(" ", text)
    text = _RE_NEWLINES.sub("\n\n", text)
    return text.strip()


def is_content_rich(text: str, min_cn: int = 150) -> bool:
    return sum(1 for c in text if "\u4e00" <= c <= "\u9fff") >= min_cn


# ──────────────────────────────────────────────────────────────────────────────
# 4. 文本切块
# ──────────────────────────────────────────────────────────────────────────────

def split_into_chunks(title: str, text: str,
                      chunk_size: int = 512,
                      overlap: int = 64) -> list[dict]:
    paragraphs = [p.strip() for p in re.split(r"\n+", text) if len(p.strip()) > 10]
    chunks: list[dict] = []
    buf = ""
    for para in paragraphs:
        buf += para + "\n"
        while len(buf) >= chunk_size:
            piece = buf[:chunk_size].strip()
            if len(piece) > 30:
                chunks.append({"title": title, "text": piece})
            buf = buf[chunk_size - overlap:]
    if len(buf.strip()) > 30:
        chunks.append({"title": title, "text": buf.strip()})
    return chunks


# ──────────────────────────────────────────────────────────────────────────────
# 5. GPU Embedding 编码器
# ──────────────────────────────────────────────────────────────────────────────

BGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："
BGE_PREFIXES = ("BAAI/bge-small-zh", "BAAI/bge-base-zh", "BAAI/bge-large-zh",)


class GPUEmbeddingEncoder:
    """
    多卡 GPU Embedding 编码器。

    核心优化：
    ① AMP float16 半精度：显存减半，A100 上速度约提升 1.8x
    ② DataParallel：多卡自动均分 batch
    ③ encode_passages：分批编码 + 每批后 empty_cache，防止 OOM
    ④ 向量直接 L2 归一化（normalize_embeddings=True），
       内积 == 余弦相似度，与 FAISS IndexFlatIP 匹配
    """

    def __init__(self, model_name: str,
                 device: str = "auto",
                 batch_size: int = 0,
                 use_fp16: bool = True):
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError:
            log.error("请安装: pip install torch sentence-transformers")
            sys.exit(1)

        self._torch = torch
        self.model_name = model_name
        gpu_info = detect_gpus()

        # 设备
        if device == "auto":
            self.device = "cuda" if gpu_info["available"] else "cpu"
        else:
            self.device = device

        self.use_fp16 = use_fp16 and "cuda" in self.device and gpu_info["available"]

        # 打印 GPU 信息
        log.info(f"加载 Embedding 模型: {model_name}")
        if gpu_info["available"]:
            log.info(f"检测到 {gpu_info['count']} 块 GPU:")
            for g in gpu_info["names"]:
                log.info(g)
            log.info(f"总显存: {gpu_info['total_vram_gb']:.1f} GB  "
                     f"AMP fp16: {'✓' if self.use_fp16 else '✗'}")
        else:
            log.warning("未检测到 GPU，使用 CPU（速度会很慢）")

        # 加载模型
        self._st = SentenceTransformer(model_name, device=self.device)
        self.dim: int = self._st.get_sentence_embedding_dimension()

        # fp16
        if self.use_fp16:
            self._st = self._st.half()
            log.info("模型已转换为 fp16")

        # 多卡 DataParallel
        self.multi_gpu = False
        if gpu_info["count"] > 1 and "cuda" in self.device:
            try:
                self._st[0].auto_model = torch.nn.DataParallel(
                    self._st[0].auto_model
                )
                self.multi_gpu = True
                log.info(f"DataParallel 已启用，{gpu_info['count']} 卡并行")
            except Exception as e:
                log.warning(f"DataParallel 启动失败 ({e})，降级为单卡")

        # batch size
        if batch_size > 0:
            self.batch_size = batch_size
        else:
            self.batch_size = (
                auto_batch_size(gpu_info["total_vram_gb"], self.dim)
                if gpu_info["available"] else 64
            )

        # 多卡时 batch size 乘以卡数，让每卡分到合适的量
        if self.multi_gpu:
            self.batch_size *= gpu_info["count"]

        log.info(f"向量维度={self.dim}  encode batch_size={self.batch_size}")

        # BGE query 前缀
        self.query_instruction = (
            BGE_QUERY_INSTRUCTION
            if any(model_name.startswith(p) for p in BGE_PREFIXES) else ""
        )

    # ── 编码 passage（构建索引用） ────────────────────────────────────────────

    def encode_passages(self, texts: list[str],
                        show_progress: bool = True) -> np.ndarray:
        """
        分批编码，返回 L2 归一化 float32 矩阵 (N, dim)。
        每个子批次编码后释放显存，防止 OOM。
        """
        import torch
        results: list[np.ndarray] = []
        total = len(texts)
        t0 = time.time()
        done = 0

        for start in range(0, total, self.batch_size):
            batch = texts[start: start + self.batch_size]
            with torch.cuda.amp.autocast(enabled=self.use_fp16):
                vecs = self._st.encode(
                    batch,
                    batch_size=len(batch),
                    show_progress_bar=show_progress,
                    normalize_embeddings=True,   # L2 归一化
                    convert_to_numpy=True,
                )
            results.append(vecs.astype(np.float32))
            done += len(batch)

            elapsed = time.time() - t0
            speed = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / speed if speed > 0 else 0
            log.info(f"    编码进度: {done:,}/{total:,}  "
                     f"速度={speed:,.0f} 块/s  ETA={eta:.0f}s")

            # 显存清理
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        return np.vstack(results)

    # ── 编码 query（检索时用） ────────────────────────────────────────────────

    def encode_query(self, query: str) -> np.ndarray:
        """编码单条 query（BGE 自动加前缀），返回 (1, dim) float32。"""
        import torch
        text = self.query_instruction + query if self.query_instruction else query
        with torch.cuda.amp.autocast(enabled=self.use_fp16):
            vec = self._st.encode(
                [text],
                batch_size=1,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        return vec.astype(np.float32)

    def free_gpu_memory(self):
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            log.info("GPU 显存已清理")


# ──────────────────────────────────────────────────────────────────────────────
# 6. 向量分片 I/O（断点续传）
# ──────────────────────────────────────────────────────────────────────────────

def save_shard(vecs: np.ndarray, path: Path):
    np.save(str(path), vecs.astype(np.float32))


def load_all_shards(shard_dir: Path) -> np.ndarray | None:
    shards = sorted(shard_dir.glob("shard_*.npy"))
    if not shards:
        return None
    log.info(f"合并 {len(shards)} 个向量分片 ...")
    return np.vstack([np.load(str(s)) for s in shards])


def count_encoded_vectors(shard_dir: Path) -> int:
    total = 0
    for s in sorted(shard_dir.glob("shard_*.npy")):
        arr = np.load(str(s), mmap_mode="r")
        total += arr.shape[0]
    return total


# ──────────────────────────────────────────────────────────────────────────────
# 7. FAISS 索引构建
# ──────────────────────────────────────────────────────────────────────────────

def build_faiss_index(vectors: np.ndarray,
                      use_ivf: bool = False,
                      nlist: int = 4096,
                      use_faiss_gpu: bool = False) -> faiss.Index:
    """
    构建 FAISS 索引。
      IndexFlatIP   精确内积（余弦），< 500 万块推荐，本地搜索也够快
      IndexIVFFlat  近似，> 500 万块推荐，需先 train
    向量已 L2 归一化，内积 == 余弦相似度。
    """
    n, dim = vectors.shape
    index_type = "IndexIVFFlat" if use_ivf else "IndexFlatIP"
    log.info(f"构建 FAISS 索引  type={index_type}  n={n:,}  dim={dim}  "
             f"faiss_gpu={use_faiss_gpu}")

    if use_ivf:
        quantizer = faiss.IndexFlatIP(dim)
        cpu_index = faiss.IndexIVFFlat(
            quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT
        )
        cpu_index.nprobe = 64
        train_n = min(n, 500_000)
        log.info(f"IVF 训练中（样本={train_n:,}）...")
        t0 = time.time()
        cpu_index.train(vectors[:train_n])
        log.info(f"训练完成，耗时={time.time()-t0:.1f}s")
    else:
        cpu_index = faiss.IndexFlatIP(dim)

    if use_faiss_gpu:
        try:
            res = faiss.StandardGpuResources()
            gpu_index = faiss.index_cpu_to_gpu(res, 0, cpu_index)
            log.info("FAISS add 使用 GPU ...")
            t0 = time.time()
            gpu_index.add(vectors)
            log.info(f"GPU add 完成，耗时={time.time()-t0:.1f}s")
            index = faiss.index_gpu_to_cpu(gpu_index)
        except Exception as e:
            log.warning(f"FAISS-GPU 不可用（{e}），回退到 CPU add")
            _add_in_batches(cpu_index, vectors)
            index = cpu_index
    else:
        _add_in_batches(cpu_index, vectors)
        index = cpu_index

    log.info(f"FAISS 索引完成  ntotal={index.ntotal:,}")
    return index


def _add_in_batches(index, vectors: np.ndarray, batch: int = 500_000):
    n = len(vectors)
    for start in range(0, n, batch):
        index.add(vectors[start: start + batch])
        log.info(f"  FAISS add [{min(start+batch, n):,}/{n:,}]")


# ──────────────────────────────────────────────────────────────────────────────
# 8. 文本块 I/O
# ──────────────────────────────────────────────────────────────────────────────

def save_chunks(chunks: list[dict], path: Path):
    with open(path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def load_chunks(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


# ──────────────────────────────────────────────────────────────────────────────
# 9. 打包
# ──────────────────────────────────────────────────────────────────────────────

def pack_kb(kb_dir: Path) -> Path:
    """
    将 kb_data/ 打包为 tar.gz（排除 shards/ 目录，节省空间）。
    拉到本地只需 faiss.index + chunks.jsonl + model_info.json。
    """
    pack_path = kb_dir.parent / f"{kb_dir.name}.tar.gz"
    log.info(f"打包知识库 → {pack_path}  （排除 shards/）")
    t0 = time.time()

    def _exclude(tarinfo):
        # 排除中间产物 shards/
        if "shards" in tarinfo.name:
            return None
        return tarinfo

    with tarfile.open(pack_path, "w:gz") as tar:
        tar.add(kb_dir, arcname=kb_dir.name, filter=_exclude)

    size_mb = pack_path.stat().st_size / 1024 ** 2
    log.info(f"打包完成  大小={size_mb:.0f} MB  耗时={time.time()-t0:.1f}s")
    log.info("")
    log.info("─── 拉取到本地的命令 ───────────────────────────────────────")
    log.info(f"  scp  user@server:{pack_path.resolve()} ./")
    log.info(f"  # 或")
    log.info(f"  rsync -avP --progress user@server:{pack_path.resolve()} ./")
    log.info(f"  # 解压")
    log.info(f"  tar -xzf {pack_path.name}")
    log.info("────────────────────────────────────────────────────────────")
    return pack_path


# ──────────────────────────────────────────────────────────────────────────────
# 10. 主流程
# ──────────────────────────────────────────────────────────────────────────────

def build_knowledge_base(
    input_path: str,
    output_dir: str           = "./kb_data",
    model_name: str           = "/root/autodl-tmp/bge-small-zh-v1.5",
    device: str               = "auto",
    max_articles: int | None  = None,
    chunk_size: int           = 512,
    overlap: int              = 64,
    min_cn_chars: int         = 150,
    batch_size: int           = 256,
    use_fp16: bool            = True,
    shard_size: int           = 500_000,
    use_ivf: bool             = False,
    nlist: int                = 4096,
    use_faiss_gpu: bool       = True,
    save_every: int           = 100_000,
    do_pack: bool             = False,
):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    shard_dir = out / "shards"
    shard_dir.mkdir(exist_ok=True)
    t_total = time.time()

    log.info("=" * 65)
    log.info(f"输入文件  : {input_path}")
    log.info(f"输出目录  : {out.resolve()}")
    log.info(f"Embedding : {model_name}")
    log.info(f"切块参数  : chunk_size={chunk_size}  overlap={overlap}")
    log.info(f"过滤阈值  : min_cn_chars={min_cn_chars}")
    log.info("=" * 65)

    # ── Step 1: 加载模型 ──────────────────────────────────────────────────────
    encoder = GPUEmbeddingEncoder(
        model_name, device=device,
        batch_size=batch_size,
        use_fp16=use_fp16,
    )

    # ── Step 2: 解析 XML → 切块（支持断点续传） ──────────────────────────────
    chunks_path = out / "chunks.jsonl"

    if chunks_path.exists():
        log.info("发现已有 chunks.jsonl，跳过解析（删除可重新解析）")
        all_chunks = load_chunks(chunks_path)
        log.info(f"加载 {len(all_chunks):,} 个文本块")
    else:
        all_chunks: list[dict] = []
        article_count = skip_count = 0
        t_parse = time.time()
        log.info("流式解析 XML bz2 中 ...")

        for title, wikitext in iter_wiki_articles(input_path, max_articles):
            clean = clean_wikitext(wikitext)
            if not is_content_rich(clean, min_cn_chars):
                skip_count += 1
                continue
            all_chunks.extend(split_into_chunks(title, clean, chunk_size, overlap))
            article_count += 1

            if article_count % 10_000 == 0:
                log.info(f"  {article_count:,} 篇  跳过={skip_count:,}  "
                         f"块={len(all_chunks):,}  "
                         f"耗时={time.time()-t_parse:.0f}s")
            if save_every > 0 and article_count % save_every == 0:
                save_chunks(all_chunks, chunks_path)

        save_chunks(all_chunks, chunks_path)
        log.info(f"解析完成  文章={article_count:,}  跳过={skip_count:,}  "
                 f"块={len(all_chunks):,}  耗时={time.time()-t_parse:.1f}s")

    if not all_chunks:
        log.error("无有效文本块，请检查输入文件路径和格式。")
        sys.exit(1)

    total = len(all_chunks)
    texts = [c["text"] for c in all_chunks]

    # ── Step 3: GPU Embedding 编码（分片保存，支持断点续传） ─────────────────
    already_done = count_encoded_vectors(shard_dir)

    if already_done >= total:
        log.info(f"向量已全部编码（{already_done:,} 块），跳过编码")
    else:
        if already_done > 0:
            log.info(f"断点续传：已编码 {already_done:,}，从第 {already_done:,} 块继续")

        existing_count = len(list(shard_dir.glob("shard_*.npy")))
        shard_idx = existing_count
        texts_todo = texts[already_done:]
        t_enc = time.time()
        encoded = already_done

        log.info(f"开始 GPU 编码  待编码={len(texts_todo):,} 块 ...")
        for shard_start in range(0, len(texts_todo), shard_size):
            batch_texts = texts_todo[shard_start: shard_start + shard_size]
            log.info(f"分片 shard_{shard_idx:04d}  样本={len(batch_texts):,} ...")

            vecs = encoder.encode_passages(batch_texts, show_progress=True)

            shard_path = shard_dir / f"shard_{shard_idx:04d}.npy"
            save_shard(vecs, shard_path)
            encoded += len(batch_texts)

            elapsed = time.time() - t_enc
            speed = (encoded - already_done) / elapsed if elapsed > 0 else 0
            eta = (total - encoded) / speed if speed > 0 else 0
            log.info(f"  已编码 {encoded:,}/{total:,}  "
                     f"速度={speed:,.0f} 块/s  ETA={eta:.0f}s")
            shard_idx += 1
            encoder.free_gpu_memory()

        log.info(f"编码全部完成，总耗时={time.time()-t_enc:.1f}s")

    # ── Step 4: 合并分片 → FAISS 建索引 ──────────────────────────────────────
    all_vectors = load_all_shards(shard_dir)
    assert all_vectors is not None and len(all_vectors) == total, \
        f"向量数({len(all_vectors)}) ≠ 文本块数({total})，请删除 shards/ 重跑"

    log.info(f"向量矩阵 shape={all_vectors.shape}  "
             f"内存={all_vectors.nbytes/1024**3:.2f} GB")

    index = build_faiss_index(
        all_vectors,
        use_ivf=use_ivf,
        nlist=nlist,
        use_faiss_gpu=use_faiss_gpu,
    )
    del all_vectors
    gc.collect()

    # ── Step 5: 持久化 ────────────────────────────────────────────────────────
    faiss.write_index(index, str(out / "faiss.index"))

    with open(out / "model_info.json", "w", encoding="utf-8") as f:
        json.dump({
            "model_name":        model_name,
            "dim":               encoder.dim,
            "query_instruction": encoder.query_instruction,
        }, f, ensure_ascii=False, indent=2)

    with open(out / "build_config.json", "w", encoding="utf-8") as f:
        json.dump({
            "input_file":   str(input_path),
            "model_name":   model_name,
            "device":       device,
            "use_fp16":     use_fp16,
            "chunk_size":   chunk_size,
            "overlap":      overlap,
            "min_cn_chars": min_cn_chars,
            "chunk_count":  total,
            "vector_dim":   encoder.dim,
            "index_type":   "IndexIVFFlat" if use_ivf else "IndexFlatIP",
            "nlist":        nlist if use_ivf else None,
            "build_date":   time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_time_s": round(time.time() - t_total, 1),
        }, f, ensure_ascii=False, indent=2)

    log.info("=" * 65)
    log.info("知识库构建完成！")
    log.info(f"   Embedding  : {model_name}")
    log.info(f"   向量维度   : {encoder.dim}")
    log.info(f"   文本块数   : {total:,}")
    log.info(f"   FAISS 类型 : {'IndexIVFFlat' if use_ivf else 'IndexFlatIP'}")
    log.info(f"   输出目录   : {out.resolve()}")
    log.info(f"   总耗时     : {time.time()-t_total:.1f}s")
    for fname in ["faiss.index", "chunks.jsonl", "model_info.json"]:
        p = out / fname
        if p.exists():
            log.info(f"   {fname:<22}  {p.stat().st_size/1024**2:>8.1f} MB")
    log.info("=" * 65)

    # ── Step 6: 打包（可选） ──────────────────────────────────────────────────
    if do_pack:
        pack_kb(out)


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="GPU 加速版中文维基百科 Embedding + FAISS 知识库构建器",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--output", "-o", default="./kb_data",
                   help="知识库输出目录")
    p.add_argument("--no-fp16", action="store_true",
                   help="关闭 AMP fp16（默认开启）")
    p.add_argument("--batch-size", type=int, default=256,
                   help="Embedding batch size（0=自动推断）")
    p.add_argument("--max-articles", type=int, default=50000,
                   help="最多处理文章数（调试用）")
    p.add_argument("--chunk-size", type=int, default=512,
                   help="每块字符数")
    p.add_argument("--overlap", type=int, default=64,
                   help="相邻块重叠字符数")
    p.add_argument("--min-cn-chars", type=int, default=150,
                   help="文章最少中文字符，低于此跳过")
    p.add_argument("--shard-size", type=int, default=500_000,
                   help="向量分片大小（断点续传粒度）")
    p.add_argument("--use-ivf", action="store_true",
                   help="使用 IndexIVFFlat 近似索引（> 500 万块推荐）")
    p.add_argument("--nlist", type=int, default=4096,
                   help="IVF 聚类中心数")
    p.add_argument("--faiss-gpu", action="store_true",
                   help="FAISS add 使用 GPU（需 faiss-gpu 包）")
    p.add_argument("--save-every", type=int, default=100_000,
                   help="每 N 篇文章中途保存 chunks")
    p.add_argument("--pack", action="store_true",
                   help="构建完成后打包为 tar.gz（排除 shards/）")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_knowledge_base(
        input_path    = "/root/autodl-tmp/zhwiki-20251220-pages-articles-multistream.xml.bz2",
        output_dir    = args.output,
        device        = "cuda",
        max_articles  = args.max_articles,
        chunk_size    = args.chunk_size,
        overlap       = args.overlap,
        min_cn_chars  = args.min_cn_chars,
        batch_size    = args.batch_size,
        use_fp16      = not args.no_fp16,
        shard_size    = args.shard_size,
        use_ivf       = args.use_ivf,
        nlist         = args.nlist,
        use_faiss_gpu = args.faiss_gpu,
        save_every    = args.save_every,
        do_pack       = args.pack,
    )