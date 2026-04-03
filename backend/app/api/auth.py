from flask import request,jsonify,Blueprint
from backend.app.models.user import User
from backend.app.core.security import hash_password,verify_password,create_access_token
from backend.app.database.session import db
from backend.app.utils.send_code import send_email_verification_code
import random
import re
import redis
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

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

# 发送验证码(登陆专用)
@auth_bp.route('/send_code', methods=['POST'])
def send_code():
    data = request.get_json()
    email = data.get('email')
    action="register"

    # 简单邮箱格式校验
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"error": "邮箱格式不正确"}), 400

    # 判断是否可发送验证码（限频控制）
    if redis_client.get(f"{action}_code_sent:{email}"):
        return jsonify({"error": "请勿频繁发送验证码"}), 429

    code = str(random.randint(100000, 999999))
    # 发送邮件逻辑（调用邮件服务）
    send_email_verification_code(email, code)

    redis_client.setex(f"{action}_code:{email}", 300, code)  # 5分钟有效
    redis_client.setex(f"{action}_code_sent:{email}", 60, "sent")  # 1分钟限频

    return jsonify({"message": "验证码已发送"}), 200


# 通过验证码注册
@auth_bp.route('/email_register', methods=['POST'])
def email_register():
    data = request.get_json()
    username=data.get('username')
    email = data.get('email')
    password = data.get('password')
    code = data.get('code')

    if not email or not password or not code:
        return jsonify({"error": "邮箱、密码和验证码都是必填"}), 400

    # 验证邮箱格式（简单）
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"error": "邮箱格式不正确"}), 400

    # 验证验证码
    saved_code = redis_client.get(f"register_code:{email}")
    if not saved_code or saved_code != code:
        return jsonify({"error": "验证码错误或已过期"}), 400

    # 检查邮箱是否已注册
    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify({"error": "该邮箱已注册"}), 400

    hashed_password = hash_password(password)
    new_user = User(email=email, password_hash=hashed_password,username=username)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "注册成功"}), 201


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