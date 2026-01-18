-- ============================================================
-- Chat-to-DB 完整数据库初始化脚本
-- 创建时间: 2026-01-18
-- 数据库类型: MySQL 8.0+
-- 字符集: utf8mb4
-- ============================================================

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS chatdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE chatdb;

-- 设置时区
SET time_zone = '+08:00';

-- ============================================================
-- 1. 用户模块 (User Module)
-- ============================================================

-- 用户表
CREATE TABLE IF NOT EXISTS `users` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID',
    `username` VARCHAR(100) NOT NULL UNIQUE COMMENT '用户名',
    `email` VARCHAR(255) NOT NULL UNIQUE COMMENT '电子邮箱',
    `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
    `display_name` VARCHAR(100) DEFAULT NULL COMMENT '显示名称',
    `avatar_url` VARCHAR(500) DEFAULT NULL COMMENT '头像URL',
    `role` VARCHAR(20) NOT NULL DEFAULT 'user' COMMENT '角色：admin, user',
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否激活',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `last_login_at` TIMESTAMP NULL DEFAULT NULL COMMENT '最后登录时间',
    
    INDEX `idx_users_username` (`username`),
    INDEX `idx_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ============================================================
-- 2. 数据库连接模块 (Database Connection Module)
-- ============================================================

-- 数据库连接表
CREATE TABLE IF NOT EXISTS `dbconnection` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '连接ID',
    `name` VARCHAR(255) NOT NULL UNIQUE COMMENT '连接名称',
    `db_type` VARCHAR(50) NOT NULL COMMENT '数据库类型：mysql, postgresql, sqlite等',
    `host` VARCHAR(255) NOT NULL COMMENT '主机地址',
    `port` INT NOT NULL COMMENT '端口号',
    `username` VARCHAR(255) NOT NULL COMMENT '用户名',
    `password_encrypted` VARCHAR(255) NOT NULL COMMENT '加密的密码',
    `database_name` VARCHAR(255) NOT NULL COMMENT '数据库名',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    INDEX `idx_dbconn_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='数据库连接表';

-- ============================================================
-- 3. Schema 元数据模块 (Schema Metadata Module)
-- ============================================================

-- Schema 表信息表
CREATE TABLE IF NOT EXISTS `schematable` (
    `id` INT PRIMARY KEY AUTO_INCREMENT COMMENT 'Schema表ID',
    `connection_id` INT NOT NULL COMMENT '数据库连接ID',
    `table_name` VARCHAR(255) NOT NULL COMMENT '表名',
    `description` TEXT DEFAULT NULL COMMENT '表描述',
    `ui_metadata` JSON DEFAULT NULL COMMENT 'UI元数据',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    INDEX `idx_schematable_conn` (`connection_id`),
    INDEX `idx_schematable_name` (`table_name`),
    FOREIGN KEY (`connection_id`) REFERENCES `dbconnection`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Schema表信息表';

-- Schema 列信息表
CREATE TABLE IF NOT EXISTS `schemacolumn` (
    `id` INT PRIMARY KEY AUTO_INCREMENT COMMENT 'Schema列ID',
    `table_id` INT NOT NULL COMMENT 'Schema表ID',
    `column_name` VARCHAR(255) NOT NULL COMMENT '列名',
    `data_type` VARCHAR(100) NOT NULL COMMENT '数据类型',
    `description` TEXT DEFAULT NULL COMMENT '列描述',
    `is_primary_key` BOOLEAN DEFAULT FALSE COMMENT '是否主键',
    `is_foreign_key` BOOLEAN DEFAULT FALSE COMMENT '是否外键',
    `is_unique` BOOLEAN DEFAULT FALSE COMMENT '是否唯一',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    INDEX `idx_schemacolumn_table` (`table_id`),
    INDEX `idx_schemacolumn_name` (`column_name`),
    FOREIGN KEY (`table_id`) REFERENCES `schematable`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Schema列信息表';

-- Schema 关系表
CREATE TABLE IF NOT EXISTS `schemarelationship` (
    `id` INT PRIMARY KEY AUTO_INCREMENT COMMENT '关系ID',
    `connection_id` INT NOT NULL COMMENT '数据库连接ID',
    `source_table_id` INT NOT NULL COMMENT '源表ID',
    `source_column_id` INT NOT NULL COMMENT '源列ID',
    `target_table_id` INT NOT NULL COMMENT '目标表ID',
    `target_column_id` INT NOT NULL COMMENT '目标列ID',
    `relationship_type` VARCHAR(50) DEFAULT NULL COMMENT '关系类型：1-to-1, 1-to-N, N-to-M',
    `description` TEXT DEFAULT NULL COMMENT '关系描述',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    INDEX `idx_schemarel_conn` (`connection_id`),
    INDEX `idx_schemarel_source_table` (`source_table_id`),
    INDEX `idx_schemarel_target_table` (`target_table_id`),
    FOREIGN KEY (`connection_id`) REFERENCES `dbconnection`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`source_table_id`) REFERENCES `schematable`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`source_column_id`) REFERENCES `schemacolumn`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`target_table_id`) REFERENCES `schematable`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`target_column_id`) REFERENCES `schemacolumn`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Schema关系表';

-- 值映射表 (自然语言到数据库值的映射)
CREATE TABLE IF NOT EXISTS `valuemapping` (
    `id` INT PRIMARY KEY AUTO_INCREMENT COMMENT '值映射ID',
    `column_id` INT NOT NULL COMMENT '列ID',
    `nl_term` VARCHAR(255) NOT NULL COMMENT '自然语言术语',
    `db_value` VARCHAR(255) NOT NULL COMMENT '数据库值',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    INDEX `idx_valuemap_column` (`column_id`),
    INDEX `idx_valuemap_nl_term` (`nl_term`),
    FOREIGN KEY (`column_id`) REFERENCES `schemacolumn`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='值映射表';

-- ============================================================
-- 4. Dashboard 仪表盘模块 (Dashboard Module)
-- ============================================================

-- 仪表盘表
CREATE TABLE IF NOT EXISTS `dashboards` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '仪表盘ID',
    `name` VARCHAR(255) NOT NULL COMMENT '仪表盘名称',
    `description` TEXT DEFAULT NULL COMMENT '描述',
    `owner_id` BIGINT NOT NULL COMMENT '所有者用户ID',
    `layout_config` JSON NOT NULL COMMENT '布局配置',
    `is_public` BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否公开',
    `tags` JSON DEFAULT NULL COMMENT '标签',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted_at` TIMESTAMP NULL DEFAULT NULL COMMENT '删除时间（软删除）',
    
    INDEX `idx_dashboards_owner` (`owner_id`),
    INDEX `idx_dashboards_created` (`created_at`),
    INDEX `idx_dashboards_deleted` (`deleted_at`),
    FOREIGN KEY (`owner_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='仪表盘表';

-- 仪表盘组件表
CREATE TABLE IF NOT EXISTS `dashboard_widgets` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '组件ID',
    `dashboard_id` BIGINT NOT NULL COMMENT '仪表盘ID',
    `widget_type` VARCHAR(50) NOT NULL COMMENT '组件类型：chart, table, metric等',
    `title` VARCHAR(255) NOT NULL COMMENT '组件标题',
    `connection_id` BIGINT NOT NULL COMMENT '数据库连接ID',
    `query_config` JSON NOT NULL COMMENT '查询配置',
    `chart_config` JSON DEFAULT NULL COMMENT '图表配置',
    `position_config` JSON NOT NULL COMMENT '位置配置',
    `refresh_interval` INT NOT NULL DEFAULT 0 COMMENT '刷新间隔（秒），0表示不自动刷新',
    `last_refresh_at` TIMESTAMP NULL DEFAULT NULL COMMENT '最后刷新时间',
    `data_cache` JSON DEFAULT NULL COMMENT '数据缓存',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    INDEX `idx_widgets_dashboard` (`dashboard_id`),
    INDEX `idx_widgets_connection` (`connection_id`),
    FOREIGN KEY (`dashboard_id`) REFERENCES `dashboards`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`connection_id`) REFERENCES `dbconnection`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='仪表盘组件表';

-- 仪表盘权限表
CREATE TABLE IF NOT EXISTS `dashboard_permissions` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '权限ID',
    `dashboard_id` BIGINT NOT NULL COMMENT '仪表盘ID',
    `user_id` BIGINT NOT NULL COMMENT '用户ID',
    `permission_level` VARCHAR(20) NOT NULL COMMENT '权限级别：owner, editor, viewer',
    `granted_by` BIGINT NOT NULL COMMENT '授权人用户ID',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    
    INDEX `idx_dashperm_dashboard` (`dashboard_id`),
    INDEX `idx_dashperm_user` (`user_id`),
    FOREIGN KEY (`dashboard_id`) REFERENCES `dashboards`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`granted_by`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='仪表盘权限表';

-- ============================================================
-- 5. AI Agent 配置模块 (AI Agent Configuration Module)
-- ============================================================

-- LLM 配置表
CREATE TABLE IF NOT EXISTS `llm_configuration` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'LLM配置ID',
    `provider` VARCHAR(50) NOT NULL COMMENT 'LLM提供商：openai, deepseek, aliyun等',
    `api_key` VARCHAR(500) DEFAULT NULL COMMENT 'API密钥（建议加密存储）',
    `base_url` VARCHAR(500) DEFAULT NULL COMMENT 'API基础URL',
    `model_name` VARCHAR(100) NOT NULL COMMENT '模型名称',
    `model_type` VARCHAR(20) NOT NULL DEFAULT 'chat' COMMENT '模型类型：chat, embedding',
    `is_active` BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    INDEX `idx_llmconfig_provider` (`provider`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='LLM配置表';

-- Agent 配置表
CREATE TABLE IF NOT EXISTS `agent_profile` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'Agent配置ID',
    `name` VARCHAR(100) NOT NULL UNIQUE COMMENT 'Agent名称',
    `role_description` TEXT DEFAULT NULL COMMENT '角色描述',
    `system_prompt` TEXT DEFAULT NULL COMMENT '系统提示词',
    `tools` JSON DEFAULT NULL COMMENT '工具列表配置',
    `llm_config_id` BIGINT DEFAULT NULL COMMENT 'LLM配置ID',
    `is_active` BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    `is_system` BOOLEAN DEFAULT FALSE COMMENT '是否系统Agent',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    INDEX `idx_agent_name` (`name`),
    FOREIGN KEY (`llm_config_id`) REFERENCES `llm_configuration`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent配置表';

-- ============================================================
-- 6. 查询历史模块 (Query History Module)
-- ============================================================

-- 查询历史表
CREATE TABLE IF NOT EXISTS `query_history` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '查询历史ID',
    `query_text` TEXT NOT NULL COMMENT '查询文本',
    `embedding` JSON DEFAULT NULL COMMENT '查询向量嵌入（JSON格式）',
    `connection_id` BIGINT DEFAULT NULL COMMENT '数据库连接ID',
    `meta_info` JSON DEFAULT NULL COMMENT '元信息：执行结果、耗时等',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    
    INDEX `idx_queryhistory_created` (`created_at`),
    INDEX `idx_queryhistory_connection` (`connection_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='查询历史表';

-- ============================================================
-- 7. 系统配置模块 (System Configuration Module)
-- ============================================================

-- 系统配置表
CREATE TABLE IF NOT EXISTS `system_config` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '配置ID',
    `config_key` VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键（唯一）',
    `config_value` TEXT DEFAULT NULL COMMENT '配置值',
    `description` TEXT DEFAULT NULL COMMENT '配置描述',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    INDEX `idx_system_config_key` (`config_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- 初始化默认配置：默认Embedding模型ID
INSERT INTO `system_config` (`config_key`, `config_value`, `description`) 
VALUES ('default_embedding_model_id', NULL, '默认Embedding模型的LLM配置ID')
ON DUPLICATE KEY UPDATE `description` = VALUES(`description`);

-- ============================================================
-- 初始化完成
-- ============================================================

-- 显示所有表
SELECT 
    '✅ 数据库初始化完成！' as Status,
    COUNT(*) as TableCount 
FROM information_schema.tables 
WHERE table_schema = 'chatdb';

-- 显示所有表的详细信息
SELECT 
    table_name as TableName,
    table_comment as Comment,
    table_rows as Rows
FROM information_schema.tables 
WHERE table_schema = 'chatdb'
ORDER BY table_name;
