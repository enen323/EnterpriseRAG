# EnterpriseRAG — 企业级RAG知识库问答系统

## 项目概述

基于LangChain + Chroma + BGE Embedding + DeepSeek API 的检索增强生成问答系统。支持PDF/Markdown/TXT上传、语义检索、重排序、LLM生成带引用的答案。

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.14 |
| 编排 | LangChain 0.3+ |
| Embedding | BAAI/bge-large-zh-v1.5 |
| 向量库 | Chroma（开发）|
| Rerank | BAAI/bge-reranker-v2-m3 |
| LLM | DeepSeek API（外部）|
| 文档解析 | Unstructured / PyPDF2 + python-docx |
| 分块 | RecursiveCharacterTextSplitter (chunk_size=512, overlap=128) |
| UI | Streamlit |
| 部署 | Docker Compose（可选）|

## 项目结构目标

```
EnterpriseRAG/
├── app.py                  # Streamlit UI
├── document_loader.py      # 文档加载与分块
├── vector_store.py         # 向量存储与检索
├── reranker.py             # 重排序模块
├── qa_chain.py             # 问答链 + 引用输出
├── config.py               # 配置（API key、模型参数等）
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── tests/
    ├── test_loader.py
    ├── test_retrieval.py
    └── test_qa.py
```

## 核心数据流

**入库**: 文档上传 → 解析文本 → 递归切分 → Embedding → 存入Chroma

**问答**: 用户问题 → Embedding → 检索Top-20 → Rerank取Top-5 → 构造Prompt → 调用LLM → 解析引用返回

## 关键指标

- Recall@5 ≥ 85%（有Rerank目标92%）
- 端到端延迟 ≤ 3s
- Rouqe-L ≥ 0.45

## 开发阶段

| 阶段 | 任务 | 产出 |
|------|------|------|
| 1 | 环境搭建 | 可运行hello world |
| 2 | 文档加载与分块 | `document_loader.py` + 测试 |
| 3 | 向量存储与检索 | `vector_store.py` + Top-K测试 |
| 4 | Rerank集成 | `reranker.py` + 效果对比 |
| 5 | LLM问答链 | `qa_chain.py` + 可回答问题 |
| 6 | Streamlit UI | `app.py` 可交互演示 |
| 7 | 性能调优 | 最佳参数记录 |
| 8 | README + 演示 | GitHub仓库完整 |

## 命令

```bash
# 虚拟环境
python -m venv .venv && source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 运行 UI
streamlit run app.py

# 运行 API
uvicorn api:app --reload

# 测试
pytest tests/ -v
```

## 代码规范

- 类型注解必须（Python 3.14 native types）
- 函数/方法写 docstring，说明参数与返回值
- 配置集中到 `config.py`，禁止硬编码 API key
- 异常处理：API调用用tenacity重试+指数退避
- 日志用 `logging` 模块，关键节点打印

## 检索配置参考

- chunk_size: 512, overlap: 128（初始）
- retriever top_k: 20
- rerank top_k: 5
- LLM temperature: 0.1（低温度保确定性）

## 简历亮点（文档原话）

> 设计并实现了基于LangChain + Chroma + BGE Embedding + DeepSeek API 的文档问答系统，支持PDF/Markdown上传与自动索引。引入BGE-Reranker重排序模型，将检索准确率（Recall@5）从78%提升至92%。实现答案溯源功能。系统平均响应延迟2.8秒。
