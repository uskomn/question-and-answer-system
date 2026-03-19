from flask import Blueprint,request,jsonify
from flask_jwt_extended import jwt_required
from backend.app.core.security import login_required


health_bp=Blueprint('health',__name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    model_loaded=True
    model_name="test"
    return jsonify({
        "status": "ready" if model_loaded else "loading",
        "model_name": model_name,
        "device": "cuda"
    })