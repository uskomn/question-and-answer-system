from flask import Blueprint,jsonify,request

info_bp=Blueprint('info',__name__)

@info_bp.route('/api/model/info', methods=['GET'])
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
