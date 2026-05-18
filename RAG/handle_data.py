"""
build_kb_en.py  ——  GPU-accelerated Embedding + FAISS Knowledge Base Builder
             for English Wikipedia
==============================================================================
Designed for compute servers:
  • Auto-detects all GPUs, multi-GPU parallel Embedding encoding
  • AMP float16 inference (half VRAM, ~1.5-2x faster)
  • Vector sharding to disk (shard_*.npy), supports resume from checkpoint
  • Auto-packs kb_data.tar.gz after build for easy download

Pipeline:
  XML bz2 line-by-line parse → Wikitext clean → chunk (512 chars)
    → GPU Embedding batch encode (multi-GPU DataParallel)
    → Save vector shards to kb_data/shards/
    → Merge shards → FAISS IndexFlatIP
    → Persist → (optional) pack

Server dependencies:
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    pip install sentence-transformers faiss-gpu tqdm numpy

Recommended Embedding models (English):
    BAAI/bge-small-en-v1.5          dim=384   33M   fastest
    BAAI/bge-base-en-v1.5           dim=768   102M  balanced  <- default
    BAAI/bge-large-en-v1.5          dim=1024  326M  best quality
    sentence-transformers/all-MiniLM-L6-v2   dim=384  very fast, good quality

Usage:
    # Full build (auto-uses all GPUs)
    python build_kb_en.py --input enwiki-20251201-pages-articles-multistream.xml.bz2

    # Debug: process only 50k articles
    python build_kb_en.py --input enwiki-*.xml.bz2 --max-articles 50000

    # Specify model + pack after build
    python build_kb_en.py --input enwiki-*.xml.bz2 \\
        --model BAAI/bge-large-en-v1.5 --pack

    # Use approximate index for very large datasets (>5M chunks)
    python build_kb_en.py --input enwiki-*.xml.bz2 --use-ivf
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
import os

print("当前工作目录:", os.getcwd())
print("脚本所在目录:", os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# 1. GPU detection
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
    """Recommend encode batch size based on total VRAM (conservative 40%)."""
    safe = total_vram_gb * 0.40 * 1024 ** 3
    bytes_per_sample = dim * 2 * 64        # fp16, conservative factor
    raw = int(safe / bytes_per_sample)
    raw = max(128, min(2048, raw))
    return 2 ** int(np.log2(raw))


# ──────────────────────────────────────────────────────────────────────────────
# 2. XML line-by-line parser
# ──────────────────────────────────────────────────────────────────────────────
# multistream bz2 cannot be handled by iterparse; use line-by-line reading

# English Wikipedia namespace prefixes to skip (non-article pages)
SKIP_TITLE_PREFIXES = (
    "Wikipedia:",
    "Help:",
    "Template:",
    "Category:",
    "Portal:",
    "Talk:",
    "File:",
    "Image:",
    "Module:",
    "MediaWiki:",
    "User:",
    "Draft:",
    "TimedText:",
    "Special:",
    "Book:",
    "Education Program:",
    "Gadget:",
    "Gadget definition:",
)

_RE_TITLE    = re.compile(r"<title>(.*?)</title>")
_RE_NS       = re.compile(r"<ns>(\d+)</ns>")
_RE_TEXT_ONE = re.compile(r"<text[^>]*>(.*?)</text>", re.DOTALL)
_RE_TEXT_BGN = re.compile(r"<text[^>]*>(.*)")


def iter_wiki_articles(bz2_path: str, max_articles: int | None = None):
    """
    Read bz2 XML line by line, yield (title, wikitext).
    Compatible with multistream format.
    Only yields main namespace (ns=0), non-redirect articles.
    """
    count   = 0
    title   = None
    ns_val  = None
    in_text = False
    buf: list[str] = []

    with bz2.open(bz2_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            # ── New page: reset state ─────────────────────────────────────────
            if "<page>" in line:
                title   = None
                ns_val  = None
                in_text = False
                buf     = []
                continue

            # ── Title ─────────────────────────────────────────────────────────
            if "<title>" in line:
                m = _RE_TITLE.search(line)
                if m:
                    title = m.group(1)
                continue

            # ── Namespace ─────────────────────────────────────────────────────
            if "<ns>" in line:
                m = _RE_NS.search(line)
                if m:
                    ns_val = m.group(1)
                continue

            # ── Text content ──────────────────────────────────────────────────
            if "<text" in line and not in_text:
                # Case A: <text ...>content</text> on one line
                m = _RE_TEXT_ONE.search(line)
                if m:
                    wikitext = m.group(1)
                    if _should_keep(ns_val, title, wikitext):
                        yield title, wikitext
                        count += 1
                        if max_articles and count >= max_articles:
                            return
                else:
                    # Case B: multi-line <text>
                    m2 = _RE_TEXT_BGN.search(line)
                    buf = [m2.group(1)] if m2 else []
                    in_text = True
                continue

            if in_text:
                if "</text>" in line:
                    buf.append(line[:line.index("</text>")])
                    wikitext = "".join(buf)
                    in_text  = False
                    buf      = []
                    if _should_keep(ns_val, title, wikitext):
                        yield title, wikitext
                        count += 1
                        if max_articles and count >= max_articles:
                            return
                else:
                    buf.append(line)


def _should_keep(ns_val: str | None, title: str | None, wikitext: str) -> bool:
    """Return True if this page should be included in the knowledge base."""
    if ns_val != "0":
        return False
    if not title:
        return False
    if any(title.startswith(p) for p in SKIP_TITLE_PREFIXES):
        return False
    # Skip redirects
    first_line = wikitext.strip().lower()
    if first_line.startswith("#redirect"):
        return False
    return True


# ──────────────────────────────────────────────────────────────────────────────
# 3. Wikitext cleaning
# ──────────────────────────────────────────────────────────────────────────────

_RE_TEMPLATE   = re.compile(r"\{\{[^{}]*?\}\}", re.DOTALL)
_RE_LINK_FILE  = re.compile(r"\[\[(?:File|Image):[^\]]*?\]\]", re.I)
_RE_LINK_CAT   = re.compile(r"\[\[(?:Category):[^\]]*?\]\]", re.I)
_RE_WIKILINK   = re.compile(r"\[\[(?:[^|\]]*?\|)?([^\]]*?)\]\]")
_RE_EXT_LINK   = re.compile(r"\[https?://\S+\s*([^\]]*?)\]")
_RE_REF        = re.compile(r"<ref[^>]*>.*?</ref>", re.DOTALL)
_RE_REF_EMPTY  = re.compile(r"<ref[^/]*/?>")
_RE_HEADING    = re.compile(r"={2,6}(.+?)={2,6}")
_RE_HTML       = re.compile(r"<[^>]+>")
_RE_HTML_ENT   = re.compile(r"&[a-zA-Z]+;|&#\d+;")
_RE_SPACES     = re.compile(r"[^\S\n]{2,}")
_RE_NEWLINES   = re.compile(r"\n{3,}")


def clean_wikitext(text: str) -> str:
    """Strip Wikitext markup and return plain English text."""
    # Remove nested templates iteratively
    for _ in range(6):
        new = _RE_TEMPLATE.sub("", text)
        if new == text:
            break
        text = new
    text = _RE_LINK_FILE.sub("", text)
    text = _RE_LINK_CAT.sub("", text)
    text = _RE_WIKILINK.sub(r"\1", text)        # keep display text
    text = _RE_EXT_LINK.sub(r"\1", text)
    text = _RE_REF.sub("", text)                # remove <ref>...</ref>
    text = _RE_REF_EMPTY.sub("", text)          # remove self-closing <ref/>
    text = _RE_HEADING.sub(r"\1", text)         # keep heading text
    text = _RE_HTML.sub("", text)
    text = _RE_HTML_ENT.sub("", text)
    # Remove wiki table rows (lines starting with | or !)
    lines = [l for l in text.splitlines()
             if not l.strip().startswith("|") and not l.strip().startswith("!")]
    text = "\n".join(lines)
    text = text.replace("'''", "").replace("''", "")
    text = text.replace("__NOTOC__", "").replace("__TOC__", "")
    text = _RE_SPACES.sub(" ", text)
    text = _RE_NEWLINES.sub("\n\n", text)
    return text.strip()


def is_content_rich(text: str, min_chars: int = 200) -> bool:
    """
    Check if the article has enough meaningful English content.
    Counts non-whitespace characters (simpler and more reliable than
    counting English letters, since cleaned text may contain numbers/punctuation).
    """
    return len(text.replace(" ", "").replace("\n", "")) >= min_chars


# ──────────────────────────────────────────────────────────────────────────────
# 4. Text chunking
# ──────────────────────────────────────────────────────────────────────────────

def split_into_chunks(title: str, text: str,
                      chunk_size: int = 512,
                      overlap: int = 64) -> list[dict]:
    """
    Split text into chunks of ~chunk_size characters with overlap.
    Paragraph boundaries are respected where possible.
    Each chunk carries its source article title.
    """
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
# 5. GPU Embedding encoder
# ──────────────────────────────────────────────────────────────────────────────

# BGE English models use a retrieval instruction prefix on queries (not passages)
BGE_EN_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
BGE_EN_PREFIXES = (
    "BAAI/bge-small-en",
    "BAAI/bge-base-en",
    "BAAI/bge-large-en",
    "BAAI/bge-m3",
)


class GPUEmbeddingEncoder:
    """
    Multi-GPU Embedding encoder backed by sentence-transformers.

    Optimizations:
      ① AMP float16: half VRAM, ~1.8x faster on A100
      ② DataParallel: auto-splits batch across all GPUs
      ③ encode_passages: sub-batch encoding + empty_cache to prevent OOM
      ④ L2-normalized vectors: inner product == cosine similarity (matches FAISS IndexFlatIP)
    """

    def __init__(self, model_name: str,
                 device: str = "auto",
                 batch_size: int = 0,
                 use_fp16: bool = True):
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError:
            log.error("Please install: pip install torch sentence-transformers")
            sys.exit(1)

        self._torch    = torch
        self.model_name = model_name
        gpu_info       = detect_gpus()

        # Device selection
        if device == "auto":
            self.device = "cuda" if gpu_info["available"] else "cpu"
        else:
            self.device = device

        self.use_fp16 = use_fp16 and "cuda" in self.device and gpu_info["available"]

        # Log GPU info
        log.info(f"Loading Embedding model: {model_name}")
        if gpu_info["available"]:
            log.info(f"Detected {gpu_info['count']} GPU(s):")
            for g in gpu_info["names"]:
                log.info(g)
            log.info(f"Total VRAM: {gpu_info['total_vram_gb']:.1f} GB  "
                     f"AMP fp16: {'enabled' if self.use_fp16 else 'disabled'}")
        else:
            log.warning("No GPU detected — using CPU (will be slow)")

        # Load model
        self._st  = SentenceTransformer(model_name, device=self.device)
        self.dim: int = self._st.get_sentence_embedding_dimension()

        # Convert to fp16
        if self.use_fp16:
            self._st = self._st.half()
            log.info("Model converted to fp16")

        # Multi-GPU DataParallel
        self.multi_gpu = False
        if gpu_info["count"] > 1 and "cuda" in self.device:
            try:
                self._st[0].auto_model = torch.nn.DataParallel(
                    self._st[0].auto_model
                )
                self.multi_gpu = True
                log.info(f"DataParallel enabled across {gpu_info['count']} GPUs")
            except Exception as e:
                log.warning(f"DataParallel failed ({e}), falling back to single GPU")

        # Batch size
        if batch_size > 0:
            self.batch_size = batch_size
        else:
            self.batch_size = (
                auto_batch_size(gpu_info["total_vram_gb"], self.dim)
                if gpu_info["available"] else 64
            )

        if self.multi_gpu:
            self.batch_size *= gpu_info["count"]

        log.info(f"Vector dim={self.dim}  encode batch_size={self.batch_size}")

        # BGE query instruction (applied at search time, not here)
        self.query_instruction = (
            BGE_EN_QUERY_INSTRUCTION
            if any(model_name.startswith(p) for p in BGE_EN_PREFIXES) else ""
        )

    def encode_passages(self, texts: list[str],
                        show_progress: bool = True) -> np.ndarray:
        """
        Encode a list of passages, return L2-normalized float32 matrix (N, dim).
        Sub-batches + empty_cache prevent OOM on large datasets.
        """
        import torch
        results: list[np.ndarray] = []
        total = len(texts)
        t0    = time.time()
        done  = 0

        for start in range(0, total, self.batch_size):
            batch = texts[start: start + self.batch_size]
            with torch.cuda.amp.autocast(enabled=self.use_fp16):
                vecs = self._st.encode(
                    batch,
                    batch_size=len(batch),
                    show_progress_bar=show_progress,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                )
            results.append(vecs.astype(np.float32))
            done += len(batch)

            elapsed = time.time() - t0
            speed   = done / elapsed if elapsed > 0 else 0
            eta     = (total - done) / speed if speed > 0 else 0
            log.info(f"    Encoded {done:,}/{total:,}  "
                     f"speed={speed:,.0f} chunks/s  ETA={eta:.0f}s")

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        return np.vstack(results)

    def encode_query(self, query: str) -> np.ndarray:
        """Encode a single query string; BGE models prepend instruction. Returns (1, dim)."""
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
            log.info("GPU memory cleared")


# ──────────────────────────────────────────────────────────────────────────────
# 6. Vector shard I/O (checkpoint / resume)
# ──────────────────────────────────────────────────────────────────────────────

def save_shard(vecs: np.ndarray, path: Path):
    np.save(str(path), vecs.astype(np.float32))


def load_all_shards(shard_dir: Path) -> np.ndarray | None:
    shards = sorted(shard_dir.glob("shard_*.npy"))
    if not shards:
        return None
    log.info(f"Merging {len(shards)} vector shards ...")
    return np.vstack([np.load(str(s)) for s in shards])


def count_encoded_vectors(shard_dir: Path) -> int:
    total = 0
    for s in sorted(shard_dir.glob("shard_*.npy")):
        arr = np.load(str(s), mmap_mode="r")
        total += arr.shape[0]
    return total


# ──────────────────────────────────────────────────────────────────────────────
# 7. FAISS index construction
# ──────────────────────────────────────────────────────────────────────────────

def build_faiss_index(vectors: np.ndarray,
                      use_ivf: bool = False,
                      nlist: int = 4096,
                      use_faiss_gpu: bool = False) -> faiss.Index:
    """
    Build a FAISS index from an L2-normalized float32 matrix.

    IndexFlatIP   exact cosine, recommended for <5M chunks
    IndexIVFFlat  approximate cosine, recommended for >5M chunks (requires train)

    Inner product == cosine similarity because vectors are L2-normalized.
    """
    n, dim     = vectors.shape
    index_type = "IndexIVFFlat" if use_ivf else "IndexFlatIP"
    log.info(f"Building FAISS index  type={index_type}  n={n:,}  dim={dim}  "
             f"faiss_gpu={use_faiss_gpu}")

    if use_ivf:
        quantizer  = faiss.IndexFlatIP(dim)
        cpu_index  = faiss.IndexIVFFlat(
            quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT
        )
        cpu_index.nprobe = 64
        train_n = min(n, 500_000)
        log.info(f"Training IVF index (samples={train_n:,}) ...")
        t0 = time.time()
        cpu_index.train(vectors[:train_n])
        log.info(f"Training done in {time.time()-t0:.1f}s")
    else:
        cpu_index = faiss.IndexFlatIP(dim)

    if use_faiss_gpu:
        try:
            res       = faiss.StandardGpuResources()
            gpu_index = faiss.index_cpu_to_gpu(res, 0, cpu_index)
            log.info("FAISS add on GPU ...")
            t0 = time.time()
            gpu_index.add(vectors)
            log.info(f"GPU add done in {time.time()-t0:.1f}s")
            index = faiss.index_gpu_to_cpu(gpu_index)
        except Exception as e:
            log.warning(f"FAISS-GPU unavailable ({e}), falling back to CPU add")
            _add_in_batches(cpu_index, vectors)
            index = cpu_index
    else:
        _add_in_batches(cpu_index, vectors)
        index = cpu_index

    log.info(f"FAISS index done  ntotal={index.ntotal:,}")
    return index


def _add_in_batches(index, vectors: np.ndarray, batch: int = 50_000):
    n = len(vectors)
    for start in range(0, n, batch):
        index.add(vectors[start: start + batch])
        log.info(f"  FAISS add [{min(start+batch, n):,}/{n:,}]")


# ──────────────────────────────────────────────────────────────────────────────
# 8. Chunk I/O
# ──────────────────────────────────────────────────────────────────────────────

def save_chunks(chunks: list[dict], path: Path):
    with open(path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def load_chunks(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


# ──────────────────────────────────────────────────────────────────────────────
# 9. Packaging
# ──────────────────────────────────────────────────────────────────────────────

def pack_kb(kb_dir: Path) -> Path:
    """
    Pack kb_data/ into a tar.gz, excluding shards/ (intermediate files).
    Only faiss.index + chunks.jsonl + model_info.json are needed locally.
    """
    pack_path = kb_dir.parent / f"{kb_dir.name}.tar.gz"
    log.info(f"Packing knowledge base → {pack_path}  (excluding shards/)")
    t0 = time.time()

    def _exclude(tarinfo):
        if "shards" in tarinfo.name:
            return None
        return tarinfo

    with tarfile.open(pack_path, "w:gz") as tar:
        tar.add(kb_dir, arcname=kb_dir.name, filter=_exclude)

    size_mb = pack_path.stat().st_size / 1024 ** 2
    log.info(f"Pack done  size={size_mb:.0f} MB  time={time.time()-t0:.1f}s")
    log.info("")
    log.info("─── Download to local machine ──────────────────────────────")
    log.info(f"  scp  user@server:{pack_path.resolve()} ./")
    log.info(f"  # or")
    log.info(f"  rsync -avP --progress user@server:{pack_path.resolve()} ./")
    log.info(f"  # extract")
    log.info(f"  tar -xzf {pack_path.name}")
    log.info("────────────────────────────────────────────────────────────")
    return pack_path


# ──────────────────────────────────────────────────────────────────────────────
# 10. Main pipeline
# ──────────────────────────────────────────────────────────────────────────────

def build_knowledge_base(
    input_path: str,
    output_dir: str           = "./RAG/kb_data_en",
    model_name: str           = "./RAG/models/bge-base-en-v1.5",
    device: str               = "auto",
    max_articles: int | None  = None,
    chunk_size: int           = 512,
    overlap: int              = 64,
    min_chars: int            = 128,
    batch_size: int           = 0,
    use_fp16: bool            = True,
    shard_size: int           = 500_000,
    use_ivf: bool             = False,
    nlist: int                = 4096,
    use_faiss_gpu: bool       = False,
    save_every: int           = 100_000,
    do_pack: bool             = False,
):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    shard_dir = out / "shards"
    shard_dir.mkdir(exist_ok=True)
    t_total = time.time()

    log.info("=" * 65)
    log.info(f"Input file  : {input_path}")
    log.info(f"Output dir  : {out.resolve()}")
    log.info(f"Embedding   : {model_name}")
    log.info(f"Chunk params: chunk_size={chunk_size}  overlap={overlap}")
    log.info(f"Filter      : min_chars={min_chars}")
    log.info("=" * 65)

    # ── Step 1: Load Embedding model ─────────────────────────────────────────
    encoder = GPUEmbeddingEncoder(
        model_name, device=device,
        batch_size=batch_size,
        use_fp16=use_fp16,
    )

    # ── Step 2: Parse XML → chunks (with resume support) ─────────────────────
    chunks_path = out / "chunks.jsonl"

    if chunks_path.exists():
        log.info("Found existing chunks.jsonl, skipping parse (delete to re-parse)")
        all_chunks = load_chunks(chunks_path)
        log.info(f"Loaded {len(all_chunks):,} chunks")
    else:
        all_chunks: list[dict] = []
        article_count = skip_count = 0
        t_parse = time.time()
        log.info("Parsing XML bz2 line by line ...")

        for title, wikitext in iter_wiki_articles(input_path, max_articles):
            clean = clean_wikitext(wikitext)
            if not is_content_rich(clean, min_chars):
                skip_count += 1
                continue
            all_chunks.extend(split_into_chunks(title, clean, chunk_size, overlap))
            article_count += 1

            if article_count % 10_000 == 0:
                log.info(f"  {article_count:,} articles  skipped={skip_count:,}  "
                         f"chunks={len(all_chunks):,}  "
                         f"elapsed={time.time()-t_parse:.0f}s")
            if save_every > 0 and article_count % save_every == 0:
                save_chunks(all_chunks, chunks_path)

        save_chunks(all_chunks, chunks_path)
        log.info(f"Parse done  articles={article_count:,}  skipped={skip_count:,}  "
                 f"chunks={len(all_chunks):,}  elapsed={time.time()-t_parse:.1f}s")

    if not all_chunks:
        log.error("No valid chunks found. Check input file path and format.")
        sys.exit(1)

    total = len(all_chunks)
    texts = [c["text"] for c in all_chunks]

    # ── Step 3: GPU Embedding encode (sharded, with resume) ──────────────────
    already_done = count_encoded_vectors(shard_dir)

    if already_done >= total:
        log.info(f"All vectors already encoded ({already_done:,} chunks), skipping")
    else:
        if already_done > 0:
            log.info(f"Resuming from checkpoint: {already_done:,} done, "
                     f"continuing from chunk {already_done:,}")

        existing_count = len(list(shard_dir.glob("shard_*.npy")))
        shard_idx  = existing_count
        texts_todo = texts[already_done:]
        t_enc      = time.time()
        encoded    = already_done

        log.info(f"Starting GPU encoding  remaining={len(texts_todo):,} chunks ...")
        for shard_start in range(0, len(texts_todo), shard_size):
            batch_texts = texts_todo[shard_start: shard_start + shard_size]
            log.info(f"Shard shard_{shard_idx:04d}  size={len(batch_texts):,} ...")

            vecs = encoder.encode_passages(batch_texts, show_progress=True)

            shard_path = shard_dir / f"shard_{shard_idx:04d}.npy"
            save_shard(vecs, shard_path)
            encoded += len(batch_texts)

            elapsed = time.time() - t_enc
            speed   = (encoded - already_done) / elapsed if elapsed > 0 else 0
            eta     = (total - encoded) / speed if speed > 0 else 0
            log.info(f"  Encoded {encoded:,}/{total:,}  "
                     f"speed={speed:,.0f} chunks/s  ETA={eta:.0f}s")
            shard_idx += 1
            encoder.free_gpu_memory()

        log.info(f"Encoding complete  total elapsed={time.time()-t_enc:.1f}s")

    # ── Step 4: Merge shards → FAISS index ───────────────────────────────────
    all_vectors = load_all_shards(shard_dir)
    assert all_vectors is not None and len(all_vectors) == total, \
        f"Vector count ({len(all_vectors)}) != chunk count ({total}). Delete shards/ and retry."

    log.info(f"Vector matrix shape={all_vectors.shape}  "
             f"memory={all_vectors.nbytes/1024**3:.2f} GB")

    index = build_faiss_index(
        all_vectors,
        use_ivf=use_ivf,
        nlist=nlist,
        use_faiss_gpu=use_faiss_gpu,
    )
    del all_vectors
    gc.collect()

    # ── Step 5: Persist ───────────────────────────────────────────────────────
    faiss.write_index(index, str(out / "faiss.index"))

    with open(out / "model_info.json", "w", encoding="utf-8") as f:
        json.dump({
            "model_name":        model_name,
            "dim":               encoder.dim,
            "query_instruction": encoder.query_instruction,
        }, f, indent=2)

    with open(out / "build_config.json", "w", encoding="utf-8") as f:
        json.dump({
            "input_file":  str(input_path),
            "model_name":  model_name,
            "device":      device,
            "use_fp16":    use_fp16,
            "chunk_size":  chunk_size,
            "overlap":     overlap,
            "min_chars":   min_chars,
            "chunk_count": total,
            "vector_dim":  encoder.dim,
            "index_type":  "IndexIVFFlat" if use_ivf else "IndexFlatIP",
            "nlist":       nlist if use_ivf else None,
            "build_date":  time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_time_s": round(time.time() - t_total, 1),
        }, f, indent=2)

    log.info("=" * 65)
    log.info("✅ Knowledge base build complete!")
    log.info(f"   Embedding model : {model_name}")
    log.info(f"   Vector dim      : {encoder.dim}")
    log.info(f"   Total chunks    : {total:,}")
    log.info(f"   FAISS type      : {'IndexIVFFlat' if use_ivf else 'IndexFlatIP'}")
    log.info(f"   Output dir      : {out.resolve()}")
    log.info(f"   Total elapsed   : {time.time()-t_total:.1f}s")
    for fname in ["faiss.index", "chunks.jsonl", "model_info.json"]:
        p = out / fname
        if p.exists():
            log.info(f"   {fname:<22}  {p.stat().st_size/1024**2:>8.1f} MB")
    log.info("=" * 65)

    # ── Step 6: Pack (optional) ───────────────────────────────────────────────
    if do_pack:
        pack_kb(out)


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="GPU-accelerated English Wikipedia Embedding + FAISS KB builder",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--output", "-o", default="./RAG/kb_data_en",
                   help="Output directory for the knowledge base")
    p.add_argument("--no-fp16", action="store_true",
                   help="Disable AMP fp16 (enabled by default)")
    p.add_argument("--batch-size", type=int, default=128,
                   help="Embedding batch size (0 = auto-infer from VRAM)")
    p.add_argument("--max-articles", type=int, default=None,
                   help="Max articles to process (for debugging)")
    p.add_argument("--chunk-size", type=int, default=512,
                   help="Characters per chunk")
    p.add_argument("--overlap", type=int, default=64,
                   help="Overlap characters between adjacent chunks")
    p.add_argument("--min-chars", type=int, default=200,
                   help="Min non-whitespace chars in article; shorter articles are skipped")
    p.add_argument("--shard-size", type=int, default=500_000,
                   help="Vectors per shard file (checkpoint granularity)")
    p.add_argument("--use-ivf", action="store_true",
                   help="Use IndexIVFFlat approximate index (recommended for >5M chunks)")
    p.add_argument("--nlist", type=int, default=4096,
                   help="Number of IVF clusters")
    p.add_argument("--faiss-gpu", action="store_true",
                   help="Run FAISS index.add on GPU (requires faiss-gpu)")
    p.add_argument("--save-every", type=int, default=100_000,
                   help="Save chunks to disk every N articles (checkpointing)")
    p.add_argument("--pack", action="store_true",
                   help="Pack output into tar.gz after build (excludes shards/)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_knowledge_base(
        input_path    = "C:/Users/uskomn/Downloads/enwiki-20251220-pages-articles-multistream.xml.bz2",
        output_dir    = args.output,
        device        = "cuda",
        max_articles  = args.max_articles,
        chunk_size    = args.chunk_size,
        overlap       = args.overlap,
        min_chars     = args.min_chars,
        batch_size    = args.batch_size,
        use_fp16      = not args.no_fp16,
        shard_size    = args.shard_size,
        use_ivf       = args.use_ivf,
        nlist         = args.nlist,
        use_faiss_gpu = args.faiss_gpu,
        save_every    = args.save_every,
        do_pack       = args.pack,
    )