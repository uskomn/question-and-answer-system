---
AIGC:
    ContentProducer: Minimax Agent AI
    ContentPropagator: Minimax Agent AI
    Label: AIGC
    ProduceID: "00000000000000000000000000000000"
    PropagateID: "00000000000000000000000000000000"
    ReservedCode1: 3045022032c3719b22b03b9a7f49300f9a7a597b37224d7a96ebc26fbddffe4cca2ad9fc022100886e5a7e85f427aad6490152a7b65ca706770d9167dd564eea423cbb33236f7e
    ReservedCode2: 3045022100998d22ca01e13608d14a01feded1c28280cc44ebd00b53563f7bf242bcea2157022070b98ba8139122180dd258d30a609c4b68534ad49a9ff00232bf04158cada5b4
---

# LiteQA - Lightweight Transformer Q&A System

基于Transformer蒸馏模型的轻量级问答系统设计与实现

## 项目简介

LiteQA 是一个基于 DistilBERT 蒸馏模型的轻量级问答系统，提供快速、高效的问答服务。系统采用前后端分离架构，前端使用 Vue 3 + Vite，后端使用 Flask。

## 技术栈

### 前端
- **框架**: Vue 3 (Composition API)
- **构建工具**: Vite
- **状态管理**: Pinia
- **HTTP 客户端**: Axios
- **Markdown 渲染**: markdown-it

### 后端
- **框架**: Flask
- **模型**: DistilBERT (distilbert-base-uncased-distilled-squad)
- **深度学习框架**: PyTorch
- **NLP 库**: Transformers

## 项目结构

```
lite-qa-system/
├── backend/                  # Flask 后端
│   ├── app.py               # 主应用入口
│   ├── requirements.txt     # Python 依赖
│   └── model/               # 模型相关文件
│
├── frontend/                 # Vue 前端
│   ├── src/
│   │   ├── api/             # API 接口
│   │   ├── assets/          # 静态资源
│   │   ├── components/      # Vue 组件
│   │   ├── stores/          # Pinia 状态管理
│   │   ├── App.vue          # 主组件
│   │   └── main.js          # 入口文件
│   ├── package.json
│   └── vite.config.js
│
└── README.md
```

## API 接口

### 1. 健康检查
- **端点**: `GET /api/health`
- **响应**:
```json
{
  "status": "ready",
  "model_name": "distilbert-base-uncased-distilled-squad",
  "device": "cuda"
}
```

### 2. 问答预测
- **端点**: `POST /api/predict`
- **请求体**:
```json
{
  "question": "What is the capital of France?",
  "context": "France is a country in Western Europe...",
  "params": {
    "temperature": 0.7,
    "max_answer_len": 50
  }
}
```
- **响应**:
```json
{
  "answer": "Paris",
  "metrics": {
    "inference_time_ms": 15.4,
    "confidence_score": 0.98
  },
  "question": "What is the capital of France?",
  "context": "France is a country..."
}
```

### 3. 批量预测
- **端点**: `POST /api/batch-predict`
- **请求体**:
```json
{
  "questions": [
    {"question": "Q1", "context": "C1"},
    {"question": "Q2", "context": "C2"}
  ]
}
```

### 4. 模型信息
- **端点**: `GET /api/model/info`

## 安装与运行

### 后端安装

```bash
cd lite-qa-system/backend

# 创建虚拟环境 (可选)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 后端运行

```bash
cd lite-qa-system/backend
python app.py
```

后端将在 `http://localhost:5000` 启动。

### 前端安装

```bash
cd lite-qa-system/frontend
npm install
```

### 前端运行

```bash
cd lite-qa-system/frontend
npm run dev
```

前端将在 `http://localhost:3000` 启动。

### 生产构建

```bash
cd lite-qa-system/frontend
npm run build
```

构建产物将生成在 `dist` 目录。

## 功能特性

1. **实时问答**: 输入问题和上下文，获取基于 DistilBERT 模型的答案
2. **性能指标**: 显示推理时间和置信度
3. **模型状态**: 实时显示模型加载状态
4. **聊天历史**: 保存对话历史，支持清除
5. **Markdown 支持**: 支持代码块等 Markdown 格式渲染
6. **错误处理**: 友好的错误提示

## 使用示例

1. 打开浏览器访问 `http://localhost:3000`
2. 等待模型加载完成（状态显示 "Ready"）
3. 在问题输入框中输入问题
4. 在上下文输入框中输入相关上下文文本
5. 点击 "Send" 按钮发送问题
6. 查看答案和性能指标

## 示例问题

**问题**: "What is machine learning?"
**上下文**: "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed. It focuses on developing algorithms that can access data and use it to learn patterns and make decisions."

## 注意事项

1. 首次运行后端时需要下载模型，可能需要一些时间
2. 确保系统有足够的内存来加载模型
3. 如果有 GPU，模型将自动使用 CUDA 加速
4. 前端默认代理 API 请求到 `http://localhost:5000`

## 许可证

MIT License

## 开发阶段
本地服务器文件目录不同
search_kb.py
search_from_kg.py
后端
查看进程
ps aux | grep gunicorn
激活虚拟环境
source venv/bin/activate
启动redis服务
sudo systemctl start redis
启动后端
gunicorn -w 2 -b 0.0.0.0:5000 "backend.app:create_app()"