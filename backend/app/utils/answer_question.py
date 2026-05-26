import torch
from transformers import AutoModelForQuestionAnswering,AutoTokenizer
from .postprocess_answer import postprocess_answers

# 本地
MODEL_PATH_D = r"E:\PycharmProjects\question and answer system\checkpoints\student_distilled"
MODEL_PATH_E = r"E:\PycharmProjects\question and answer system\checkpoints\teacher_finetuned"
# 服务器
# MODEL_PATH_D = r"/home/ubuntu/question-and-answer-system/checkpoints/exp_D_logits_attn_kd"
# MODEL_PATH_E = r"/home/ubuntu/question-and-answer-system/checkpoints/exp_E_two_stage_distill"

models = {}
tokenizers = {}

def load_model(name, path):
    tokenizer = AutoTokenizer.from_pretrained(path)
    model = AutoModelForQuestionAnswering.from_pretrained(path)

    model.to(device)
    model.eval()

    tokenizers[name] = tokenizer
    models[name] = model


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 加载多个模型
load_model("model_D", MODEL_PATH_D)
load_model("model_E", MODEL_PATH_E)


def answer_question_single(question, context, model, tokenizer, model_name, max_length=512):
    inputs = tokenizer(
        question,
        context,
        return_tensors="pt",
        truncation=True,
        max_length=max_length
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    start_logits = outputs.start_logits
    end_logits = outputs.end_logits

    start_probs = torch.softmax(start_logits, dim=-1)
    end_probs = torch.softmax(end_logits, dim=-1)

    best_score = 0
    best_span = (0, 0)

    max_answer_len = 80

    seq_len = len(start_probs[0])

    if model_name == "model_E":

        for i in range(1, seq_len):
            for j in range(i, min(i + max_answer_len, seq_len)):
                score = (start_probs[0][i] * end_probs[0][j]).item()

                if score > best_score:
                    best_score = score
                    best_span = (i, j)

        if best_score < 0.01:
            return None

    else:
        for i in range(seq_len):
            for j in range(i, min(i + max_answer_len, seq_len)):
                score = (start_probs[0][i] * end_probs[0][j]).item()
                if score > best_score:
                    best_score = score
                    best_span = (i, j)

    start_idx, end_idx = best_span

    if end_idx < start_idx:
        return None

    answer = tokenizer.convert_tokens_to_string(
        tokenizer.convert_ids_to_tokens(
            inputs["input_ids"][0][start_idx:end_idx + 1]
        )
    )

    answer = answer.strip()

    # ❗过滤特殊 token（重点）
    if any(tok in answer for tok in ["[CLS]", "[SEP]", "[PAD]"]):
        return None

    if not answer:
        return None

    return {
        "answer": answer,
        "score": best_score
    }


def answer_question_multi(question, contexts, model, tokenizer,model_name, top_k=3):
    candidates = []

    for ctx in contexts:
        result = answer_question_single(question, ctx, model, tokenizer,model_name)
        if result:
            candidates.append(result)
            candidates.append({**result, "context": ctx})

    if not candidates:
        return None

    seen = set()
    filtered = []
    for c in candidates:
        if c["answer"] not in seen:
            filtered.append(c)
            seen.add(c["answer"])

    filtered = sorted(filtered, key=lambda x: x["score"], reverse=True)

    top_candidates = filtered[:top_k]

    ctxs = [c.get("context", "") for c in top_candidates]
    final_answer = postprocess_answers(top_candidates, contexts=ctxs)

    return {
        "answer": final_answer,
        "candidates": top_candidates
    }


def answer_question(question: str, contexts: list, model_name="model_D"):
    model = models[model_name]
    tokenizer = tokenizers[model_name]

    result = answer_question_multi(question, contexts, model, tokenizer,model_name)
    if model_name == "model_E" and result is None:
        print("model_E失败，自动切换model_D")
        result = answer_question_multi(question, contexts, models["model_D"], tokenizers["model_D"],"model_D")
    if result is None or not isinstance(result, dict):
        return "知识库中暂无切合信息"

    if "answer" not in result:
        return "知识库中暂无切合信息"
    print("处理前")
    print(result['answer'])
    final_answer = postprocess_answers(
        result["candidates"],
        contexts=contexts,  # ← 新增，直接传原文列表
        top_k=1,  # 建议从1开始，答案更干净
    )
    print("处理后")
    print(final_answer)

    return final_answer if result else None

def answer_question_context(question: str, context: str, model_name: str = "model_D") -> str:
    model = models[model_name]
    tokenizer = tokenizers[model_name]

    result = answer_question_single(question, context, model, tokenizer, model_name)

    # 修复1：result 为 None 或缺少 answer 字段时统一兜底
    if not result or "answer" not in result:
        return "知识库中暂无切合信息"

    # 修复2：复用后处理逻辑（清洗 + 句子扩展）
    candidate = [{"answer": result["answer"], "score": result["score"]}]
    final_answer = postprocess_answers(candidate, contexts=[context], top_k=1)

    return final_answer
