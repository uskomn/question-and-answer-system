from flask import Blueprint,jsonify,request
from flask_jwt_extended import jwt_required
from backend.app.core.security import login_required

info_bp=Blueprint('info',__name__)

@info_bp.route('/model/info', methods=['GET'])
@login_required
@jwt_required()
def model_info():
    """Get model information"""
    return jsonify({
        "model_name": "model_name",
        "model_type": "DistilBERT",
        "description": "Distilled BERT model for Question Answering",
        "max_length": 512,
        "loaded": "model_loaded",
        "device": "cuda"
    })
