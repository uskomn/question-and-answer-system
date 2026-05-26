# postprocess_answer.py
import re
import difflib


def expand_to_sentence(answer: str, context: str) -> str:
    """
    在原文中找到 answer 所在位置，向前/后扩展到完整句子边界。
    找不到时原样返回。
    """
    idx = context.find(answer)
    if idx == -1:
        # 做一次 fuzzy 匹配兜底
        best_ratio, best_pos = 0, -1
        window = len(answer) + 20
        for i in range(0, len(context) - len(answer) + 1, 5):
            ratio = difflib.SequenceMatcher(
                None, answer, context[i: i + window]
            ).ratio()
            if ratio > best_ratio:
                best_ratio, best_pos = ratio, i
        if best_ratio < 0.5:
            return answer
        idx = best_pos

    # 向左找句子起点（. ! ? \n 之后）
    sent_start = idx
    for sep in ".!?\n":
        pos = context.rfind(sep, 0, idx)
        if pos != -1:
            sent_start = max(sent_start, pos + 1)

    # 向右找句子终点
    sent_end = len(context)
    for sep in ".!?\n":
        pos = context.find(sep, idx + len(answer))
        if pos != -1:
            sent_end = min(sent_end, pos + 1)

    expanded = context[sent_start:sent_end].strip()
    # 扩展结果不能比原始答案短太多，防止误截
    return expanded if len(expanded) >= len(answer) else answer


def clean_text(text: str) -> str:
    """修复 tokenizer 还原后的常见格式问题。"""
    # 去掉 BERT 的 ## subword 拼接符
    text = text.replace(" ##", "")
    # 修复数字列表：1 ) → 1)
    text = re.sub(r"(\d)\s+\)", r"\1)", text)
    # 修复冒号/逗号前多余空格
    text = re.sub(r"\s+([,;:!?.])", r"\1", text)
    # 修复左括号后多余空格
    text = re.sub(r"\(\s+", "(", text)
    # 合并连续空格
    text = re.sub(r" {2,}", " ", text)
    # 首字母大写
    text = text.strip()
    if text:
        text = text[0].upper() + text[1:]
    return text


def is_similar(a: str, b: str, threshold: float = 0.7) -> bool:
    """语义重复检测（基于字符级相似度）。"""
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() > threshold


def score_candidate(candidate: dict) -> float:
    """
    综合评分 = 模型置信度 × 长度惩罚。
    过短的答案（< 5字符）和过长的答案都降权。
    """
    score = candidate["score"]
    length = len(candidate["answer"])
    if length < 5:
        score *= 0.3
    elif length > 200:
        score *= 0.8
    else:
        # 适中长度给小奖励
        score *= 1.0 + min(length / 200, 0.2)
    return score


def postprocess_answers(
        candidates: list,
        contexts: list = None,
        top_k: int = 1,
        sim_threshold: float = 0.65,
) -> str:
    """
    主后处理入口。

    candidates: [{"answer": str, "score": float}, ...]
    contexts:   对应的原文列表（用于句子扩展），可选
    top_k:      最终保留答案数（建议 1~2）
    """
    if not candidates:
        return "知识库中暂无切合信息"

    results = []
    for i, c in enumerate(candidates):
        ans = c["answer"]

        # ① 文本清洗
        ans = clean_text(ans)
        if not ans:
            continue

        # ② 句子扩展（需要传入 contexts）
        if contexts and i < len(contexts):
            ans = expand_to_sentence(ans, contexts[i])
            ans = clean_text(ans)  # 扩展后再清洗一遍

        results.append({"answer": ans, "score": c["score"]})

    if not results:
        return "知识库中暂无切合信息"

    # ③ 按综合评分排序
    results.sort(key=score_candidate, reverse=True)

    # ④ 语义去重
    deduped = []
    for r in results:
        if not any(is_similar(r["answer"], d["answer"], sim_threshold) for d in deduped):
            deduped.append(r)
        if len(deduped) >= top_k:
            break

    # ⑤ 拼接（多候选用句号分隔，更自然）
    final = "。".join(d["answer"].rstrip("。") for d in deduped)
    return final