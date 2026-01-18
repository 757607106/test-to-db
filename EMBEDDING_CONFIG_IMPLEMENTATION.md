# Embedding模型配置化改造 - 实施总结

## 📋 概述

本次改造将系统中硬编码的Embedding模型逻辑替换为可配置模式，用户可在Admin后台新增和管理Embedding模型，系统动态加载并使用用户配置的模型。

**实施日期**: 2026-01-18  
**状态**: ✅ 已完成

---

## 🎯 实现的功能

### 1. 数据库层

#### 新增表: `system_config`
- 存储系统级配置，包括默认Embedding模型ID
- 支持灵活的键值对配置

**迁移文件**: `backend/alembic/versions/004_add_system_config.py`

#### 新增模型和CRUD
- `SystemConfig` 模型 (`backend/app/models/system_config.py`)
- `SystemConfig` Schema (`backend/app/schemas/system_config.py`)
- `CRUDSystemConfig` (`backend/app/crud/crud_system_config.py`)

### 2. 后端核心功能

#### 统一Embedding工厂 (`backend/app/core/llms.py`)

新增函数:
- `get_default_embedding_config()` - 从数据库获取默认Embedding配置
- `create_embedding_from_config()` - 根据配置创建Embedding实例
- `get_default_embedding_model_v2()` - 新版获取Embedding模型（优先数据库）

支持的Provider:
- ✅ OpenAI
- ✅ Azure OpenAI
- ✅ DeepSeek
- ✅ Aliyun (阿里云)
- ✅ Ollama
- ✅ 其他OpenAI兼容API

#### VectorService重构 (`backend/app/services/hybrid_retrieval_service.py`)

改进:
- 构造函数接受 `llm_config: LLMConfiguration` 参数
- 支持从数据库配置初始化
- 统一的初始化逻辑（不再区分provider）
- `VectorServiceFactory` 新增 `create_service_from_config()` 方法
- `get_default_service()` 优先使用数据库配置

### 3. API接口

#### 新增端点 (`backend/app/api/api_v1/endpoints/system_config.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/system-config/{config_key}` | 获取配置 |
| PUT | `/api/system-config/{config_key}` | 更新配置 |
| POST | `/api/system-config/default-embedding/{llm_config_id}` | 设置默认Embedding |
| DELETE | `/api/system-config/default-embedding` | 清除默认Embedding |
| GET | `/api/system-config/default-embedding/current` | 获取当前默认Embedding |

### 4. 前端改进

#### Admin页面增强 (`frontend/admin/src/pages/LLMConfig/index.tsx`)

新功能:
- ⭐ 显示当前默认Embedding模型的"默认"徽章
- ⭐ Embedding类型配置行显示"设为默认"按钮
- ⭐ 当前默认模型显示"清除默认"按钮
- 🔄 Provider选择器支持下拉选择和手动输入
- 🎨 视觉提示优化

#### 新增Service (`frontend/admin/src/services/systemConfig.ts`)
- `getDefaultEmbeddingModel()` - 获取默认Embedding
- `setDefaultEmbeddingModel()` - 设置默认Embedding
- `clearDefaultEmbeddingModel()` - 清除默认Embedding

### 5. 迁移工具

#### 环境变量迁移脚本 (`backend/scripts/migrate_embedding_config.py`)

功能:
- 检查环境变量中的Embedding配置
- 自动创建对应的`llm_configuration`记录
- 设置为默认Embedding模型
- 支持 Aliyun, Ollama, OpenAI 配置

使用方法:
```bash
cd backend
python scripts/migrate_embedding_config.py
```

### 6. 测试

#### 集成测试 (`backend/tests/test_embedding_config.py`)

测试覆盖:
- ✅ SystemConfig CRUD操作
- ✅ 创建Embedding配置
- ✅ 获取默认配置
- ✅ OpenAI Embedding实例创建
- ✅ Ollama Embedding实例创建
- ✅ VectorService初始化
- ✅ VectorServiceFactory默认服务
- ✅ 配置验证

---

## 🔄 数据流

### 配置阶段

```
用户在Admin添加Embedding
    ↓
POST /api/llm-configs
    ↓
保存到 llm_configuration 表
    ↓
用户点击"设为默认"
    ↓
POST /api/system-config/default-embedding/{id}
    ↓
更新 system_config 表
    ↓
清除 VectorService 缓存
```

### 运行时加载

```
HybridRetrievalEngine 初始化
    ↓
VectorServiceFactory.get_default_service()
    ↓
get_default_embedding_config()
    ↓
查询 system_config.default_embedding_model_id
    ↓
查询 llm_configuration (id=xxx)
    ↓
create_service_from_config(config)
    ↓
VectorService(llm_config=config)
    ↓
根据 provider 初始化对应的 Embedding 实例
```

### Fallback机制

```
数据库无配置
    ↓
检查环境变量
    ↓
VECTOR_SERVICE_TYPE = "aliyun"
    ↓
使用 DASHSCOPE_API_KEY, DASHSCOPE_EMBEDDING_MODEL
    ↓
创建 OpenAIEmbeddings 实例
```

---

## 📊 影响的文件

### 后端 (11个文件)

**新建**:
1. `backend/alembic/versions/004_add_system_config.py`
2. `backend/app/models/system_config.py`
3. `backend/app/schemas/system_config.py`
4. `backend/app/crud/crud_system_config.py`
5. `backend/app/api/api_v1/endpoints/system_config.py`
6. `backend/scripts/migrate_embedding_config.py`
7. `backend/tests/test_embedding_config.py`

**修改**:
8. `backend/app/core/llms.py` - 新增Embedding工厂函数
9. `backend/app/services/hybrid_retrieval_service.py` - 重构VectorService
10. `backend/app/api/api_v1/api.py` - 添加system_config路由
11. `backend/app/crud/__init__.py` - 导出system_config

### 前端 (2个文件)

**新建**:
1. `frontend/admin/src/services/systemConfig.ts`

**修改**:
2. `frontend/admin/src/pages/LLMConfig/index.tsx` - UI增强

---

## 🚀 使用指南

### 1. 运行数据库迁移

```bash
cd backend
alembic upgrade head
```

### 2. (可选) 迁移现有环境变量配置

```bash
cd backend
python scripts/migrate_embedding_config.py
```

### 3. 在Admin后台配置Embedding模型

1. 访问 Admin 后台 → 模型配置管理
2. 点击"新建配置"
3. 选择模型类型为"嵌入 (Embedding)"
4. 填写Provider、模型名称、API Key等信息
5. 保存后，点击"⭐"图标设为默认

### 4. 验证配置

```bash
# 查看当前默认Embedding
curl http://localhost:8000/api/system-config/default-embedding/current

# 测试VectorService是否正常工作
# 在系统中执行一次查询，检查日志中的Embedding模型初始化信息
```

---

## ⚠️ 注意事项

### 1. 维度兼容性

不同Embedding模型的维度不同:
- OpenAI text-embedding-3-small: 1536维
- OpenAI text-embedding-3-large: 3072维
- Ollama qwen3-embedding:0.6b: 1024维

**切换模型时需要重建Milvus索引！**

### 2. 缓存清理

切换默认Embedding后，系统会自动清理 `VectorServiceFactory._instances` 缓存。如果手动修改数据库，需要重启服务。

### 3. API密钥安全

当前API密钥以明文存储在数据库中。生产环境建议:
- 使用数据库加密
- 使用密钥管理服务 (如 AWS KMS, Azure Key Vault)
- 限制数据库访问权限

### 4. 向后兼容

系统完全向后兼容:
- 如果数据库无配置，自动fallback到环境变量
- 现有的环境变量配置继续有效
- 不影响已部署的系统

---

## 🧪 测试验证清单

- [x] 用户在Admin新增OpenAI Embedding，设为默认，查询历史功能正常
- [x] 用户在Admin新增Ollama Embedding，设为默认，混合检索正常
- [x] 数据库无配置时，fallback到环境变量正常
- [x] 切换默认Embedding后，VectorService实例正确更新
- [x] 多provider（OpenAI, Ollama, Aliyun）同时存在时切换正常
- [x] 迁移脚本正确执行
- [x] API接口返回正确数据
- [x] 前端UI正确显示默认标记

---

## 📚 相关文档

- [计划文档](/.cursor/plans/embedding模型配置化改造_7b47f65c.plan.md)
- [数据库Schema文档](/docs/backend/DATABASE_SCHEMA.md)
- [阿里云向量配置文档](/docs/ALIYUN_VECTOR_SETUP.md)

---

## 🎉 总结

本次改造成功实现了Embedding模型的配置化管理，提升了系统的灵活性和可维护性。用户现在可以:

1. ✅ 在Admin后台可视化管理Embedding模型
2. ✅ 支持多种Provider（OpenAI, Ollama, Aliyun等）
3. ✅ 动态切换默认Embedding模型
4. ✅ 保持向后兼容，支持环境变量fallback
5. ✅ 提供完整的迁移工具和测试用例

系统架构更加清晰，代码更易维护，为未来扩展更多Provider奠定了基础。
