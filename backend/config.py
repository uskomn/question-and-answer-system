import os
from dotenv import load_dotenv

load_dotenv()
# 服务器Mysql密码是aqzdwsfN2%
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "aeijcmejsiefmeiaeigr")
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MODEL_PATH=os.getenv("/root/")

