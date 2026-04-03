from flask import Blueprint,jsonify,request
from flask_jwt_extended import jwt_required
from backend.app.core.security import login_required
from backend.app.utils.answer_question import answer_question
from backend.app.utils.search_from_kg import search_from_kg

qa_bp=Blueprint("qa",__name__)

@qa_bp.route("/question_answer", methods=["POST"])
@login_required
@jwt_required()
def qa():
    data = request.json

    question = data.get("question")
    if not question:
        return jsonify({"error": "Missing question"}), 400

    contexts = search_from_kg(question, top_k=3)
    if not contexts:
        return jsonify({"error": "No context found"}), 400

    answer = answer_question(question, contexts)

    if answer is None:
        return jsonify({
            "question": question,
            "answer": "抱歉，未在知识库中找到相关答案。",
            "found": False
        })

    return jsonify({
        "question": question,
        "answer": answer,
        "found": True
    })
