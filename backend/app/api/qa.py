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
    context = search_from_kg(question)
    print(context)

    if not question or not context:
        return jsonify({"error": "Missing question or context"}), 400

    answer = answer_question(question, context[0])

    return jsonify({
        "question": question,
        "answer": answer
    })
