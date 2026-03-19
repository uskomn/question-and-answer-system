from flask import request,jsonify,Blueprint
from backend.app.models.user import User
from backend.app.core.security import hash_password,verify_password,create_access_token
from backend.app.database.session import db

auth_bp=Blueprint('auth',__name__)

# 注册
@auth_bp.route('/register',methods=['POST'])
def register():
    data=request.get_json()
    if not data:
        return jsonify({"message":"no valid request"}),400
    username=data.get("username")
    email=data.get("email")
    password=data.get("password")
    if not username or not email or not password:
        return jsonify({"message":"username or email or password is required"}),400
    user=User.query.filter_by(username=username).first()
    if user:
        return jsonify({"message":"this username is already registered"}),400
    user=User.query.filter_by(email=email).first()
    if user:
        return jsonify({"message":"this email is already registered"}),400
    hashed_password=hash_password(password)

    new_user=User(username=username,email=email,password_hash=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    db.session.refresh(new_user)

    return jsonify({
        "user_id": new_user.id,
        "username": new_user.username,
        "email": new_user.email
    }), 201

# 登录
@auth_bp.route('/login', methods=["POST"])
def login():
    data=request.get_json()
    print(data)
    if not data:
        return jsonify({"message":"no valid request"}),400
    username=data.get("username")
    password=data.get("password")
    if not username or not password:
        return jsonify({"message":"username or password is required"}),400
    user=User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"message":"the user is not exist"}),400
    if not verify_password(password,user.password_hash):
        return jsonify({"message":"wrong password"}),400

    access_token=create_access_token({"sub": str(user.id)})

    return jsonify({
        "access_token":access_token,
        "token_type":"bearer",
        "user_id":user.id,
        "username":user.username
    }),200