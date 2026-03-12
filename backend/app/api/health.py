from flask import Blueprint,request,jsonify


health_bp=Blueprint('health',__name__)

@health_bp.route('/api/health', methods=['GET'])
def health_check():
    model_loaded=True
    model_name="test"
    return jsonify({
        "status": "ready" if model_loaded else "loading",
        "model_name": model_name,
        "device": "cuda"
    })