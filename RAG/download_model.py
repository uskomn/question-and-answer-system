# download_model.py
# ================================
# 用于下载 HuggingFace 模型到本地（离线使用）
# ================================

from huggingface_hub import snapshot_download
import os

# ====== 配置区 ======
MODEL_NAME = "BAAI/bge-base-zh-v1.5"   # 可改 small / large
SAVE_DIR = "./models/bge-base-zh-v1.5"  # 本地保存路径

# ====================

def main():
    print(f"开始下载模型: {MODEL_NAME}")
    print(f"保存路径: {SAVE_DIR}")

    os.makedirs(SAVE_DIR, exist_ok=True)

    snapshot_download(
        repo_id=MODEL_NAME,
        local_dir=SAVE_DIR,
        local_dir_use_symlinks=False,  # 避免软链接问题（很重要）
        resume_download=True           # 支持断点续传
    )

    print("\n下载完成！")
    print(f"模型已保存到: {os.path.abspath(SAVE_DIR)}")


if __name__ == "__main__":
    main()