# 阿里云向量服务配置说明

## ✅ 已完成的修改

系统已成功修改为使用阿里云DashScope的text-embedding-v4向量嵌入服务，不再依赖Ollama。

## 📝 配置步骤

### 1. 获取阿里云API Key

访问：https://help.aliyun.com/zh/model-studio/get-api-key

注意：新加坡和北京地域的API Key不同。

### 2. 设置环境变量

在 `backend/.env` 文件中添加以下配置：

```bash
# 阿里云DashScope配置（必需）
DASHSCOPE_API_KEY=sk-your-api-key-here

# 向量服务类型（必需）
VECTOR_SERVICE_TYPE=aliyun

# 阿里云地域配置（可选，默认北京）
# 北京地域（默认）
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 或新加坡地域
# DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1

# 嵌入模型（可选，默认text-embedding-v4）
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
```

### 3. 重启后端服务

```bash
cd backend
python admin_server.py
```

## 🔧 修改的文件

### 1. `app/core/config.py`
添加了阿里云配置项：
- `DASHSCOPE_API_KEY`: API密钥
- `DASHSCOPE_BASE_URL`: API地址
- `DASHSCOPE_EMBEDDING_MODEL`: 嵌入模型名称
- `VECTOR_SERVICE_TYPE`: 默认改为"aliyun"

### 2. `app/services/hybrid_retrieval_service.py`
增强了 `VectorService` 类以支持阿里云：
- 添加 `_initialize_aliyun()` 方法
- 修改 `_embed_with_retry()` 支持阿里云API
- 添加 `_batch_embed_aliyun()` 方法
- 修改 `_embed_batch_with_retry()` 支持阿里云批量嵌入

## 🎯 功能特性

### 支持的向量服务
- ✅ **aliyun**: 阿里云DashScope（推荐，默认）
- ✅ **ollama**: 本地Ollama服务
- ⚠️ **sentence_transformer**: 本地模型（需额外配置）

### 阿里云优势
- ☁️ 云端服务，无需本地部署
- 🚀 性能稳定，响应快速
- 💰 按量计费，成本可控
- 🌐 支持多地域部署

### 自动重试机制
- 最多重试3次
- 指数退避策略
- 详细错误日志

### 批量处理
- 自动分批处理大量文本
- 默认批次大小：32
- 支持缓存机制

## 📊 API调用示例

系统会自动调用阿里云API，格式如下：

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

response = client.embeddings.create(
    model="text-embedding-v4",
    input="用户问题"
)

embedding = response.data[0].embedding
```

## 🧪 测试验证

### 1. 测试向量服务初始化

```python
from app.services.hybrid_retrieval_service import VectorServiceFactory

# 初始化服务
service = await VectorServiceFactory.get_default_service()

# 测试嵌入
embedding = await service.embed_question("测试问题")
print(f"向量维度: {len(embedding)}")
```

### 2. 测试问答对保存

在聊天界面点赞一个回答，查看后端日志：

```
INFO: Vector service initialized successfully with aliyun
INFO: Aliyun DashScope model loaded, dimension: 1024
```

### 3. 验证数据保存

```sql
SELECT * FROM hybrid_qa_pairs 
WHERE query_type = 'USER_FEEDBACK' 
ORDER BY created_at DESC 
LIMIT 1;
```

## ⚠️ 常见问题

### Q1: "DASHSCOPE_API_KEY is not set"
**解决**: 确保在 `.env` 文件中设置了 `DASHSCOPE_API_KEY`

### Q2: 连接超时
**解决**: 
- 检查网络连接
- 确认API地址正确
- 检查防火墙设置

### Q3: "Invalid API key"
**解决**:
- 确认API Key正确
- 检查是否使用了正确地域的Key
- 确认账户余额充足

### Q4: 向量维度不匹配
**解决**:
- text-embedding-v4 默认维度是1024
- 确保Milvus集合使用正确的维度

## 🔄 切换回Ollama（可选）

如果需要切换回Ollama服务：

```bash
# .env
VECTOR_SERVICE_TYPE=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=qwen3-embedding:0.6b
```

然后重启服务。

## 📈 性能对比

| 服务类型 | 响应时间 | 稳定性 | 部署难度 | 成本 |
|---------|---------|--------|---------|------|
| 阿里云  | 快      | 高     | 低      | 按量 |
| Ollama  | 中      | 中     | 中      | 免费 |
| SentenceTransformer | 慢 | 高 | 高 | 免费 |

## 💡 最佳实践

1. **生产环境**: 推荐使用阿里云服务
2. **开发环境**: 可使用Ollama节省成本
3. **离线环境**: 使用SentenceTransformer
4. **启用缓存**: 减少API调用次数
5. **批量处理**: 提高处理效率

## 📚 相关文档

- [阿里云DashScope文档](https://help.aliyun.com/zh/dashscope/)
- [text-embedding-v4模型说明](https://help.aliyun.com/zh/model-studio/developer-reference/text-embedding-v4)
- [OpenAI兼容API说明](https://help.aliyun.com/zh/dashscope/developer-reference/compatibility-of-openai-with-dashscope/)

---

**更新日期**: 2026-01-13  
**版本**: 1.0.0  
**状态**: ✅ 已完成并测试
