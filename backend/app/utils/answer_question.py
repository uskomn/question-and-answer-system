import torch
from transformers import AutoModelForQuestionAnswering,AutoTokenizer
from .postprocess_answer import postprocess_answers


MODEL_PATH_D = r"E:\PycharmProjects\question and answer system\checkpoints\exp_D_logits_attn_kd"
MODEL_PATH_E = r"E:\PycharmProjects\question and answer system\checkpoints\exp_E_two_stage_distill"

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


def answer_question_single(question, context, model, tokenizer, max_length=512):
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

    # 👉 用概率更稳定
    start_probs = torch.softmax(start_logits, dim=-1)
    end_probs = torch.softmax(end_logits, dim=-1)

    best_score = 0
    best_span = (0, 0)

    max_answer_len = 40  # 控制答案长度

    for i in range(len(start_probs[0])):
        for j in range(i, min(i + max_answer_len, len(end_probs[0]))):
            score = (start_probs[0][i] * end_probs[0][j]).item()
            if score > best_score:
                best_score = score
                best_span = (i, j)

    start_idx, end_idx = best_span

    if end_idx <= start_idx:
        return None

    answer = tokenizer.convert_tokens_to_string(
        tokenizer.convert_ids_to_tokens(
            inputs["input_ids"][0][start_idx:end_idx + 1]
        )
    )

    answer = answer.replace(" ", "").strip()

    # 👉 过滤太短答案（很重要）
    if not answer or len(answer) < 3:
        return None

    return {
        "answer": answer,
        "score": best_score
    }


# ======================
# 多段 QA + rerank（核心）
# ======================
def answer_question_multi(question, contexts, model, tokenizer, top_k=3):
    candidates = []

    for ctx in contexts:
        result = answer_question_single(question, ctx, model, tokenizer)
        if result:
            candidates.append(result)

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

    final_answer = "；".join([c["answer"] for c in top_candidates])

    return {
        "answer": final_answer,
        "candidates": top_candidates
    }


def answer_question(question: str, contexts: list, model_name="model_D"):
    model = models[model_name]
    tokenizer = tokenizers[model_name]

    result = answer_question_multi(question, contexts, model, tokenizer)
    print("处理前")
    print(result['answer'])
    final_answer = postprocess_answers(result["candidates"])
    print("处理后")
    print(final_answer)

    return final_answer if result else None
