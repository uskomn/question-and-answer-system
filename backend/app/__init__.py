from flask import Flask
from flask_cors import CORS
from backend.app.database.session import db
from backend.config import Config
from flask_jwt_extended import JWTManager
from backend.app.api.auth import auth_bp
from backend.app.api.health import health_bp
from backend.app.api.model_info import info_bp
from  backend.app.api.predict import predict_bp
from backend.app.api.qa import qa_bp

jwt=JWTManager()

def create_app():
    app=Flask(__name__)
    CORS(app,supports_credentials=True)
    app.config.from_object(Config)
    db.init_app(app)
    jwt.init_app(app)

    app.register_blueprint(auth_bp,url_prefix='/api/auth')
    app.register_blueprint(info_bp,url_prefix='/api/info')
    app.register_blueprint(health_bp,url_prefix='/api/health')
    app.register_blueprint(predict_bp,url_prefix='/api/predict')
    app.register_blueprint(qa_bp,url_prefix='/api/qa')

    return app