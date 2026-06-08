from flask import Blueprint,jsonify,request
from flask_jwt_extended import jwt_required
from backend.app.core.security import login_required
from backend.app.utils.answer_question import answer_question,answer_question_context
from backend.app.utils.search_from_kg import search_from_kg

qa_bp=Blueprint("qa",__name__)

@qa_bp.route("/question_answer", methods=["POST"])
@login_required
@jwt_required()
def qa():
    data = request.json

    question = data.get("question")
    context=data.get("context")
    model_name=data.get("model",'model_D')
    if not question:
        return jsonify({"error": "Missing question"}), 400
    kb_results = None
    if context:
        print("上下文问答模式")
        answer=answer_question_context(question,context,model_name=model_name)
    else:
        print("知识库问答模式")
        kb_results = search_from_kg(question, top_k=3)
        print(f"使用模型{model_name}")
        if not kb_results:
            return jsonify({"error": "No context found"}), 400

        contexts = [r["text"] for r in kb_results]
        answer = answer_question(question, contexts, model_name=model_name)

        if answer is None:
            return jsonify({
                "question": question,
                "answer": "抱歉，未在知识库中找到相关答案。",
                "contexts": kb_results,
                "found": False
            })

    return jsonify({
        "question": question,
        "answer": answer,
        "contexts": kb_results if not context else None,
        "found": True
    })
