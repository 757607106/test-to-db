# LLM 配置选择修复总结

## 问题
用户配置了 DeepSeek 模型，但系统仍然使用千问模型。

## 根本原因
`get_active_llm_config()` 函数按 ID 升序选择配置，导致总是使用最早创建的配置。

## 修复方案
修改排序逻辑为 ID 降序，使用最新创建的配置。

## 修改内容
**文件**: `backend/app/core/llms.py`

```python
# 修改前
.order_by(LLMConfiguration.id.asc()).first()  # 升序

# 修改后  
.order_by(LLMConfiguration.id.desc()).first()  # 降序
```

## 验证结果
✅ 测试通过！系统现在正确选择 DeepSeek（ID=9）而不是千问（ID=5）

### 当前配置状态
- ID=5: qwen3-max (千问)
- ID=7: gemini-3-flash-preview
- ID=9: deepseek-chat ✅ **被选中**

## 重要提示
⚠️ **必须重启 LangGraph 服务器才能生效！**

```bash
# 1. 停止当前服务器 (Ctrl+C)
# 2. 重新启动
langgraph dev
```

## 测试方法
重启后，在聊天页面发送消息，观察日志应该显示：
```
📡 LLM 模型初始化
   提供商: OpenAI
   模型: deepseek-chat
   API Base: https://api.deepseek.com/v1
```

## 相关文件
- 修复代码: `backend/app/core/llms.py`
- 测试脚本: `backend/test_llm_selection.py`
- 验证脚本: `backend/verify_llm_fix.py`
- 详细文档: `.kiro/specs/dynamic-agent-model-binding/BUGFIX_DEFAULT_MODEL_SELECTION.md`
