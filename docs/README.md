# Chat-to-DB 项目文档

## 📚 文档导航

### 快速开始
- [快速启动指南](getting-started/QUICK_START.md) - 5分钟快速开始
- [主README](../README.md) - 项目主页和快速入门

### 架构设计
- [架构与技术栈](ARCHITECTURE_AND_TECH_STACK.md) - 系统架构和技术栈详解
- [Agent工作流程](architecture/AGENT_WORKFLOW.md) - Agent核心逻辑流程
- [Text2SQL分析](architecture/TEXT2SQL_ANALYSIS.md) - Text2SQL系统架构分析
- [上下文工程](architecture/CONTEXT_ENGINEERING.md) - 上下文工程与记忆体

### 核心功能
- [多轮对话与数据分析](MULTI_ROUND_AND_ANALYST_FEATURES.md) - 澄清机制和数据分析功能
- [Interrupt与流式API](INTERRUPT_AND_STREAMING_GUIDE.md) - interrupt()澄清和SSE流式输出
- [项目结构说明](PROJECT_STRUCTURE.md) - 完整的项目目录结构

### 后端开发
- [数据库表结构](backend/DATABASE_SCHEMA.md) - 完整的数据库表结构说明
- [数据库初始化](backend/DATABASE_INIT.md) - 数据库初始化指南
- [数据库连接信息](backend/DATABASE_CONNECTION_INFO.md) - 数据库连接配置
- [测试数据库](backend/TEST_DATABASES.md) - 测试数据库使用说明

### LangGraph相关
- [LangGraph快速开始](langgraph/GETTING_STARTED.md) - LangGraph快速入门
- [Checkpointer设置](langgraph/CHECKPOINTER_SETUP.md) - 状态持久化配置
- [API设置指南](langgraph/API_SETUP_GUIDE.md) - LangGraph API使用
- [实施总结](langgraph/IMPLEMENTATION_SUMMARY.md) - LangGraph记忆体实施完整总结

### 部署运维
- [Docker部署](deployment/DOCKER_DEPLOYMENT.md) - Docker完整部署指南
- [Docker快速启动](deployment/DOCKER_QUICK_START.md) - Docker一键启动
- [阿里云向量服务](ALIYUN_VECTOR_SETUP.md) - 阿里云向量服务配置

## 🔍 快速查找

### 我想...
- **快速开始使用** → [快速启动指南](getting-started/QUICK_START.md)
- **了解系统架构** → [架构与技术栈](ARCHITECTURE_AND_TECH_STACK.md)
- **了解Agent工作流程** → [Agent工作流程](architecture/AGENT_WORKFLOW.md)
- **初始化数据库** → [数据库初始化](backend/DATABASE_INIT.md)
- **部署到服务器** → [Docker部署](deployment/DOCKER_DEPLOYMENT.md)
- **配置LangGraph** → [LangGraph快速开始](langgraph/GETTING_STARTED.md)

## 📝 文档说明

本文档目录仅包含实际存在的文档。如需了解更多功能，请查看各文档内的详细说明。
