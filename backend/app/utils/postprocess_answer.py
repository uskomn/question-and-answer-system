import re

def postprocess_answers(candidates, top_k=3):
    """
    通用 QA 后处理模块
    candidates: [{"answer": str, "score": float}]
    """

    # ======================
    # 1. 清洗
    # ======================
    def clean(ans):
        if not ans:
            return ""
        ans = ans.strip()

        # 去多余空格
        ans = re.sub(r"\s+", "", ans)

        # 去尾部标点（统一后面加）
        ans = ans.rstrip("。；;，,、")

        return ans

    # ======================
    # 2. 过滤无效答案
    # ======================
    answers = []
    for c in candidates:
        ans = clean(c["answer"])

        # 过滤太短/无意义
        if len(ans) < 3:
            continue

        answers.append(ans)

    if not answers:
        return None

    # ======================
    # 3. 相似去重（关键）
    # ======================
    def is_similar(a, b):
        # 包含关系
        if a in b or b in a:
            return True

        # 简单重叠率
        overlap = len(set(a) & set(b)) / max(len(set(a)), 1)
        return overlap > 0.7

    filtered = []
    for ans in answers:
        if not any(is_similar(ans, f) for f in filtered):
            filtered.append(ans)

    # ======================
    # 4. 句式修复（通用规则）
    # ======================
    def normalize_sentence(ans):
        # 如果是“是……”开头 → 保持
        if ans.startswith("是"):
            return ans

        # 如果像短语 → 不动
        if len(ans) < 8:
            return ans

        # 去掉奇怪开头（比如“其中”“此外”）
        ans = re.sub(r"^(其中|此外|另外|并且|而且)", "", ans)

        return ans

    normalized = [normalize_sentence(a) for a in filtered[:top_k]]

    # ======================
    # 5. 拼接（关键）
    # ======================
    # 判断是否适合用“；”还是“，”拼接
    final="，".join(normalized)

    return final + "。"