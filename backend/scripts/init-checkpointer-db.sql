-- LangGraph Checkpointer 数据库初始化脚本
-- 此脚本会在 PostgreSQL 容器首次启动时自动执行

-- 创建数据库（如果不存在）
-- 注意：在 docker-entrypoint-initdb.d 中，数据库已经由环境变量创建

-- 设置默认编码
SET client_encoding = 'UTF8';

-- 创建扩展（如果需要）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 授予权限
GRANT ALL PRIVILEGES ON DATABASE langgraph_checkpoints TO langgraph;

-- 输出初始化完成信息
DO $$
BEGIN
    RAISE NOTICE 'LangGraph Checkpointer database initialized successfully';
END $$;
