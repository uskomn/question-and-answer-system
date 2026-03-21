import torch
from transformers import AutoModelForQuestionAnswering,AutoTokenizer


# MODEL_PATH = "E:\PycharmProjects\question and answer system\checkpoints\exp_D_logits_attn_kd"
MODEL_PATH = "/home/ubuntu/question-and-answer-system/checkpoints/exp_D_logits_attn_kd"
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForQuestionAnswering.from_pretrained(MODEL_PATH)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()


def answer_question(question, context):
    inputs = tokenizer(
        question,
        context,
        return_tensors="pt",
        truncation=True,
        max_length=512
    )

    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    start_logits = outputs.start_logits
    end_logits = outputs.end_logits

    start_idx = torch.argmax(start_logits)
    end_idx = torch.argmax(end_logits) + 1

    answer = tokenizer.convert_tokens_to_string(
        tokenizer.convert_ids_to_tokens(
            inputs["input_ids"][0][start_idx:end_idx]
        )
    )

    return answer
