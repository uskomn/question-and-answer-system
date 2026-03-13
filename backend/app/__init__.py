from flask import Flask
from flask_cors import CORS
from backend.app.database.session import db
from backend.config import Config
from flask_jwt_extended import JWTManager
from backend.app.api.auth import auth_bp

jwt=JWTManager()

def create_app():
    app=Flask(__name__)
    CORS(app,supports_credentials=True)
    app.config.from_object(Config)
    db.init_app(app)
    jwt.init_app(app)

    app.register_blueprint(auth_bp,url_prefix='/api/auth')

    return app