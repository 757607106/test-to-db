-- ============================================================
-- Chat-to-DB 数据库迁移脚本 - 添加用户数据隔离支持
-- 执行时间: 2026-01-24
-- 描述: 为 dbconnection, query_history, agent_profile, llm_configuration 表添加 user_id 字段
-- ============================================================

USE chatdb;

-- ============================================================
-- 创建迁移存储过程
-- ============================================================

DELIMITER //

DROP PROCEDURE IF EXISTS add_user_isolation//

CREATE PROCEDURE add_user_isolation()
BEGIN
    -- 变量声明
    DECLARE col_exists INT DEFAULT 0;
    DECLARE idx_exists INT DEFAULT 0;
    
    -- ========================================
    -- 1. dbconnection 表添加 user_id
    -- ========================================
    SELECT COUNT(*) INTO col_exists FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'dbconnection' AND COLUMN_NAME = 'user_id';
    
    IF col_exists = 0 THEN
        ALTER TABLE `dbconnection` ADD COLUMN `user_id` BIGINT DEFAULT NULL COMMENT '所属用户ID' AFTER `database_name`;
        SELECT 'Added user_id to dbconnection' AS log_message;
    ELSE
        SELECT 'user_id already exists in dbconnection' AS log_message;
    END IF;
    
    -- 添加索引
    SELECT COUNT(*) INTO idx_exists FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'dbconnection' AND INDEX_NAME = 'idx_dbconn_user';
    
    IF idx_exists = 0 THEN
        CREATE INDEX `idx_dbconn_user` ON `dbconnection` (`user_id`);
        SELECT 'Added idx_dbconn_user index' AS log_message;
    END IF;
    
    -- ========================================
    -- 2. 创建 query_history 表（如果不存在）
    -- ========================================
    CREATE TABLE IF NOT EXISTS `query_history` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '查询历史ID',
        `query_text` TEXT NOT NULL COMMENT '查询文本',
        `embedding` JSON DEFAULT NULL COMMENT '查询向量嵌入',
        `connection_id` BIGINT DEFAULT NULL COMMENT '数据库连接ID',
        `user_id` BIGINT DEFAULT NULL COMMENT '所属用户ID',
        `meta_info` JSON DEFAULT NULL COMMENT '元信息',
        `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
        INDEX `idx_queryhistory_created` (`created_at`),
        INDEX `idx_queryhistory_connection` (`connection_id`),
        INDEX `idx_queryhistory_user` (`user_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='查询历史表';
    SELECT 'query_history table ready' AS log_message;
    
    -- ========================================
    -- 3. agent_profile 表添加 user_id
    -- ========================================
    SET col_exists = 0;
    SELECT COUNT(*) INTO col_exists FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'agent_profile' AND COLUMN_NAME = 'user_id';
    
    IF col_exists = 0 THEN
        ALTER TABLE `agent_profile` ADD COLUMN `user_id` BIGINT DEFAULT NULL COMMENT '所属用户ID' AFTER `llm_config_id`;
        SELECT 'Added user_id to agent_profile' AS log_message;
    ELSE
        SELECT 'user_id already exists in agent_profile' AS log_message;
    END IF;
    
    -- 添加索引
    SET idx_exists = 0;
    SELECT COUNT(*) INTO idx_exists FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'agent_profile' AND INDEX_NAME = 'idx_agent_user';
    
    IF idx_exists = 0 THEN
        CREATE INDEX `idx_agent_user` ON `agent_profile` (`user_id`);
        SELECT 'Added idx_agent_user index' AS log_message;
    END IF;
    
    -- ========================================
    -- 4. llm_configuration 表添加 user_id
    -- ========================================
    SET col_exists = 0;
    SELECT COUNT(*) INTO col_exists FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'llm_configuration' AND COLUMN_NAME = 'user_id';
    
    IF col_exists = 0 THEN
        ALTER TABLE `llm_configuration` ADD COLUMN `user_id` BIGINT DEFAULT NULL COMMENT '所属用户ID (NULL表示系统级配置)' AFTER `id`;
        SELECT 'Added user_id to llm_configuration' AS log_message;
    ELSE
        SELECT 'user_id already exists in llm_configuration' AS log_message;
    END IF;
    
    -- 添加索引
    SET idx_exists = 0;
    SELECT COUNT(*) INTO idx_exists FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'llm_configuration' AND INDEX_NAME = 'idx_llmconfig_user';
    
    IF idx_exists = 0 THEN
        CREATE INDEX `idx_llmconfig_user` ON `llm_configuration` (`user_id`);
        SELECT 'Added idx_llmconfig_user index' AS log_message;
    END IF;
    
    -- ========================================
    -- 5. 创建默认管理员用户
    -- ========================================
    INSERT INTO `users` (`username`, `email`, `password_hash`, `display_name`, `role`, `is_active`)
    SELECT 'admin', 'admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.EQZJIGEq7N1Lhe', 'Administrator', 'admin', TRUE
    FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `users` WHERE `username` = 'admin');
    SELECT 'Admin user ready (password: admin123)' AS log_message;
    
    -- ========================================
    -- 6. 更新现有数据
    -- ========================================
    UPDATE `dbconnection` SET `user_id` = (SELECT id FROM `users` WHERE `username` = 'admin' LIMIT 1) WHERE `user_id` IS NULL;
    SELECT CONCAT('Updated ', ROW_COUNT(), ' dbconnection records') AS log_message;
    
    UPDATE `agent_profile` SET `user_id` = (SELECT id FROM `users` WHERE `username` = 'admin' LIMIT 1) WHERE `user_id` IS NULL AND `is_system` = FALSE;
    SELECT CONCAT('Updated ', ROW_COUNT(), ' agent_profile records') AS log_message;
    
    -- 注意：llm_configuration 现有数据保持 user_id = NULL，作为系统级配置对所有用户可见
    SELECT 'llm_configuration existing records kept as system-level (user_id = NULL)' AS log_message;
    
    SELECT 'Migration completed successfully!' AS final_status;
END//

DELIMITER ;

-- 执行迁移
CALL add_user_isolation();

-- 清理存储过程
DROP PROCEDURE IF EXISTS add_user_isolation;

-- 显示结果
SELECT 'dbconnection' AS TableName, COUNT(*) AS TotalRows, COUNT(user_id) AS WithUserId FROM dbconnection
UNION ALL
SELECT 'agent_profile', COUNT(*), COUNT(user_id) FROM agent_profile
UNION ALL
SELECT 'query_history', COUNT(*), COUNT(user_id) FROM query_history
UNION ALL
SELECT 'llm_configuration', COUNT(*), COUNT(user_id) FROM llm_configuration;
