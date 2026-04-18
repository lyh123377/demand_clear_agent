# 美术需求澄清与结构化Agent原型

> 一个基于AI的美术需求澄清助手，通过多轮对话帮助用户明确美术需求，降低沟通成本和返工率。

## 🎯 功能特性

- **多轮对话澄清**：主动追问缺失的关键信息（类型、风格、尺寸、分层要求等）
- **RAG检索增强**：基于历史案例和规范知识库进行智能推荐
- **结构化输出**：生成标准化的需求卡片，便于存档和传递
- **实时进度跟踪**：可视化展示需求收集进度
- **中途修改支持**：随时可以修改已填写的信息

## 🛠️ 技术栈

| 技术 | 说明 |
|------|------|
| Python 3.9+ | 运行环境 |
| Flask | Web框架 |
| LangChain | Agent框架 |
| 智谱AI GLM-4-Flash | 大语言模型 |
| Chroma | 向量数据库 |
| all-MiniLM-L6-v2 | Embedding模型 |

## 📦 安装部署

### 1. 克隆项目

```bash
git clone <repository_url>
cd 需求澄清Agent
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置API密钥

复制环境变量模板并填写您的智谱AI API密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```
ZHIPUAI_API_KEY=您的智谱AI API密钥
```

> 获取智谱AI API密钥：https://open.bigmodel.cn/

### 5. 初始化知识库

```bash
python init_kb.py
```

这将构建向量数据库，包含：
- 15条美术交付规范
- 100个历史案例
- 12条常见返工原因

### 6. 启动应用

```bash
python app.py
```

访问 http://127.0.0.1:5000 即可使用。

## 🚀 快速开始

### 首次使用流程

1. 打开浏览器访问 http://127.0.0.1:5000
2. 在输入框中描述您的美术需求，例如：
   - "我需要一个角色皮肤"
   - "做一套UI图标"
   - "设计一个关卡背景"
3. 根据助手提问，逐步提供关键信息
4. 完成信息收集后，自动生成结构化需求卡片

### 对话示例

```
用户: 我需要一个角色皮肤

助手: 📋 已确认：类型：角色皮肤
      
      请描述一下期望的风格？（如：甜美、暗黑、赛博、国风、科幻等）

用户: 赛博朋克风格

助手: 📋 已确认：类型：角色皮肤 | 风格：赛博
      
      请问需要的尺寸规格是多少？（如：1024x1024、1920x1080等）

用户: 1024x2048

助手: 📋 已确认：类型：角色皮肤 | 风格：赛博 | 尺寸：1024x2048
      
      请问对分层有特殊要求吗？比如需要PSD分层、特定图层命名规则等？

...
```

## 📁 项目结构

```
需求澄清Agent/
├── app.py                    # Flask主应用
├── init_kb.py                # 初始化向量库脚本
├── agent/
│   ├── __init__.py
│   ├── llm_client.py         # 智谱AI客户端
│   ├── conversation.py       # 多轮对话管理
│   ├── rag_engine.py         # RAG检索引擎
│   └── card_generator.py     # 需求卡片生成
├── knowledge_base/
│   ├── specs.json            # 美术交付规范（15条）
│   ├── cases.json            # 历史案例（100条）
│   └── issues.json           # 返工问题（12条）
├── templates/
│   └── index.html            # Web界面模板
├── static/
│   ├── style.css             # 样式文件
│   └── script.js             # 前端交互脚本
├── requirements.txt          # Python依赖
├── .env.example              # 环境变量模板
└── README.md                 # 本文档
```

## 📋 需求卡片字段说明

| 字段 | 说明 | 必填 |
|------|------|------|
| 需求ID | 自动生成的唯一标识 | ✓ |
| 类型 | 角色皮肤/UI图标/关卡元素/推广素材 | ✓ |
| 风格 | 甜美/暗黑/赛博/国风/科幻等 | ✓ |
| 尺寸 | 具体像素尺寸 | ✓ |
| 分层要求 | PSD分层规范 | - |
| Spine预留 | 是否需要Spine动画支持 | - |
| 交付时间 | 期望交付日期 | - |
| 参考图 | 参考图片链接 | - |

## 🔧 高级配置

### 使用自己的Embedding模型

编辑 `agent/rag_engine.py` 中的 `_init_embeddings` 方法：

```python
def _init_embeddings(self):
    self.embeddings = HuggingFaceBgeEmbeddings(
        model_name="your-model-name",  # 替换为您的模型
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
```

### 修改向量检索参数

在 `agent/rag_engine.py` 的 `similarity_search` 方法中：

```python
def similarity_search(self, query: str, top_k: int = 3, threshold: float = 0.7):
    # top_k: 返回结果数量
    # threshold: 相似度阈值（0-1）
```

## 🐛 常见问题

### Q: 启动时报错 "智谱AI API Key未设置"

A: 请确保已创建 `.env` 文件并正确配置 `ZHIPUAI_API_KEY`。

### Q: 首次运行提示"未找到向量数据库"

A: 运行 `python init_kb.py` 初始化知识库。

### Q: 检索结果为空

A: 检查 `knowledge_base/` 目录下的JSON文件是否存在且格式正确。

### Q: 界面显示异常

A: 确保使用现代浏览器（Chrome/Firefox/Edge最新版本）。

## 📝 开发说明

### 添加新的规范

编辑 `knowledge_base/specs.json`，添加新的规范条目：

```json
{
    "id": 16,
    "category": "分类",
    "title": "规范标题",
    "content": "规范内容",
    "examples": "示例"
}
```

### 添加新的历史案例

编辑 `knowledge_base/cases.json`，添加新的案例：

```json
{
    "case_id": "CASE_101",
    "description": "需求描述",
    "type": "角色皮肤",
    "style": "甜美",
    "dimensions": "1024x1024",
    "layered": "是",
    "result": "成功",
    "thumbnail": "https://..."
}
```

添加后需要重新运行 `python init_kb.py` 重建索引。

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！
