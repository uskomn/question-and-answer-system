import torch
from transformers import AutoModelForQuestionAnswering,AutoTokenizer


MODEL_PATH = "E:\PycharmProjects\question and answer system\checkpoints\exp_D_logits_attn_kd"
# MODEL_PATH = "/home/ubuntu/question-and-answer-system/checkpoints/exp_D_logits_attn_kd"
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForQuestionAnswering.from_pretrained(MODEL_PATH)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()


def answer_question(question: str, contexts: list, max_length=512, score_threshold=5.0):
    merged_context = "\n".join(contexts)

    inputs = tokenizer(
        question,
        merged_context,
        return_tensors="pt",
        truncation=True,
        max_length=max_length
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    start_logits = outputs.start_logits
    end_logits = outputs.end_logits

    # 置信度过滤
    score = (torch.max(start_logits) + torch.max(end_logits)).item()
    if score < score_threshold:
        return None

    start_idx = torch.argmax(start_logits)
    end_idx = torch.argmax(end_logits) + 1

    # 防止边界异常
    if end_idx <= start_idx:
        return None

    answer = tokenizer.convert_tokens_to_string(
        tokenizer.convert_ids_to_tokens(
            inputs["input_ids"][0][start_idx:end_idx]
        )
    )

    # 清理中文 wordpiece 空格
    answer = answer.replace(" ", "").strip()

    return answer if answer else None
