-- ============================================================
-- Chat-to-DB 数据库迁移脚本 - 多租户支持
-- 执行时间: 2026-01-24
-- 描述: 创建租户表，为所有相关表添加 tenant_id 字段
-- ============================================================

USE chatdb;

-- ============================================================
-- 创建迁移存储过程
-- ============================================================

DELIMITER //

DROP PROCEDURE IF EXISTS add_multi_tenant_support//

CREATE PROCEDURE add_multi_tenant_support()
BEGIN
    -- 变量声明
    DECLARE col_exists INT DEFAULT 0;
    DECLARE idx_exists INT DEFAULT 0;
    DECLARE tenant1_id BIGINT DEFAULT 0;
    DECLARE tenant2_id BIGINT DEFAULT 0;
    
    -- ========================================
    -- 1. 创建租户表
    -- ========================================
    CREATE TABLE IF NOT EXISTS `tenants` (
        `id` BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '租户ID',
        `name` VARCHAR(100) NOT NULL UNIQUE COMMENT '公司标识',
        `display_name` VARCHAR(200) NOT NULL COMMENT '公司显示名称',
        `description` TEXT DEFAULT NULL COMMENT '公司描述',
        `is_active` BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否启用',
        `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
        `updated_at` TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
        INDEX `idx_tenant_name` (`name`),
        INDEX `idx_tenant_active` (`is_active`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='租户/公司表';
    SELECT 'tenants table ready' AS log_message;
    
    -- ========================================
    -- 2. 创建默认租户
    -- ========================================
    INSERT INTO `tenants` (`name`, `display_name`, `description`)
    SELECT 'renwoxing', '任我行', '任我行公司 - 系统默认租户'
    FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `tenants` WHERE `name` = 'renwoxing');
    
    INSERT INTO `tenants` (`name`, `display_name`, `description`)
    SELECT 'test_company', '测试公司', '测试公司 - 用于测试的租户'
    FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM `tenants` WHERE `name` = 'test_company');
    
    SELECT id INTO tenant1_id FROM `tenants` WHERE `name` = 'renwoxing' LIMIT 1;
    SELECT id INTO tenant2_id FROM `tenants` WHERE `name` = 'test_company' LIMIT 1;
    SELECT CONCAT('Created tenants: renwoxing=', tenant1_id, ', test_company=', tenant2_id) AS log_message;
    
    -- ========================================
    -- 3. users 表添加 tenant_id 和 permissions
    -- ========================================
    SELECT COUNT(*) INTO col_exists FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'users' AND COLUMN_NAME = 'tenant_id';
    
    IF col_exists = 0 THEN
        ALTER TABLE `users` ADD COLUMN `tenant_id` BIGINT DEFAULT NULL COMMENT '所属租户ID' AFTER `id`;
        SELECT 'Added tenant_id to users' AS log_message;
    ELSE
        SELECT 'tenant_id already exists in users' AS log_message;
    END IF;
    
    SELECT COUNT(*) INTO col_exists FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'users' AND COLUMN_NAME = 'permissions';
    
    IF col_exists = 0 THEN
        ALTER TABLE `users` ADD COLUMN `permissions` JSON DEFAULT NULL COMMENT '菜单/功能权限配置' AFTER `role`;
        SELECT 'Added permissions to users' AS log_message;
    END IF;
    
    -- 添加索引
    SET idx_exists = 0;
    SELECT COUNT(*) INTO idx_exists FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'users' AND INDEX_NAME = 'idx_user_tenant';
    
    IF idx_exists = 0 THEN
        CREATE INDEX `idx_user_tenant` ON `users` (`tenant_id`);
        SELECT 'Added idx_user_tenant index' AS log_message;
    END IF;
    
    -- ========================================
    -- 4. dbconnection 表添加 tenant_id
    -- ========================================
    SET col_exists = 0;
    SELECT COUNT(*) INTO col_exists FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'dbconnection' AND COLUMN_NAME = 'tenant_id';
    
    IF col_exists = 0 THEN
        ALTER TABLE `dbconnection` ADD COLUMN `tenant_id` BIGINT DEFAULT NULL COMMENT '所属租户ID' AFTER `user_id`;
        SELECT 'Added tenant_id to dbconnection' AS log_message;
    END IF;
    
    SET idx_exists = 0;
    SELECT COUNT(*) INTO idx_exists FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'dbconnection' AND INDEX_NAME = 'idx_dbconn_tenant';
    
    IF idx_exists = 0 THEN
        CREATE INDEX `idx_dbconn_tenant` ON `dbconnection` (`tenant_id`);
        SELECT 'Added idx_dbconn_tenant index' AS log_message;
    END IF;
    
    -- ========================================
    -- 5. llm_configuration 表添加 tenant_id
    -- ========================================
    SET col_exists = 0;
    SELECT COUNT(*) INTO col_exists FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'llm_configuration' AND COLUMN_NAME = 'tenant_id';
    
    IF col_exists = 0 THEN
        ALTER TABLE `llm_configuration` ADD COLUMN `tenant_id` BIGINT DEFAULT NULL COMMENT '所属租户ID' AFTER `user_id`;
        SELECT 'Added tenant_id to llm_configuration' AS log_message;
    END IF;
    
    SET idx_exists = 0;
    SELECT COUNT(*) INTO idx_exists FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'llm_configuration' AND INDEX_NAME = 'idx_llmconfig_tenant';
    
    IF idx_exists = 0 THEN
        CREATE INDEX `idx_llmconfig_tenant` ON `llm_configuration` (`tenant_id`);
        SELECT 'Added idx_llmconfig_tenant index' AS log_message;
    END IF;
    
    -- ========================================
    -- 6. agent_profile 表添加 tenant_id
    -- ========================================
    SET col_exists = 0;
    SELECT COUNT(*) INTO col_exists FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'agent_profile' AND COLUMN_NAME = 'tenant_id';
    
    IF col_exists = 0 THEN
        ALTER TABLE `agent_profile` ADD COLUMN `tenant_id` BIGINT DEFAULT NULL COMMENT '所属租户ID' AFTER `user_id`;
        SELECT 'Added tenant_id to agent_profile' AS log_message;
    END IF;
    
    SET idx_exists = 0;
    SELECT COUNT(*) INTO idx_exists FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'agent_profile' AND INDEX_NAME = 'idx_agent_tenant';
    
    IF idx_exists = 0 THEN
        CREATE INDEX `idx_agent_tenant` ON `agent_profile` (`tenant_id`);
        SELECT 'Added idx_agent_tenant index' AS log_message;
    END IF;
    
    -- ========================================
    -- 7. query_history 表添加 tenant_id
    -- ========================================
    SET col_exists = 0;
    SELECT COUNT(*) INTO col_exists FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'query_history' AND COLUMN_NAME = 'tenant_id';
    
    IF col_exists = 0 THEN
        ALTER TABLE `query_history` ADD COLUMN `tenant_id` BIGINT DEFAULT NULL COMMENT '所属租户ID' AFTER `user_id`;
        SELECT 'Added tenant_id to query_history' AS log_message;
    END IF;
    
    SET idx_exists = 0;
    SELECT COUNT(*) INTO idx_exists FROM information_schema.STATISTICS 
    WHERE TABLE_SCHEMA = 'chatdb' AND TABLE_NAME = 'query_history' AND INDEX_NAME = 'idx_queryhistory_tenant';
    
    IF idx_exists = 0 THEN
        CREATE INDEX `idx_queryhistory_tenant` ON `query_history` (`tenant_id`);
        SELECT 'Added idx_queryhistory_tenant index' AS log_message;
    END IF;
    
    -- ========================================
    -- 8. 更新现有用户数据
    -- ========================================
    -- admin 用户属于"任我行"
    UPDATE `users` SET `tenant_id` = tenant1_id, `role` = 'tenant_admin' WHERE `username` = 'admin' AND `tenant_id` IS NULL;
    SELECT CONCAT('Updated admin user to tenant: renwoxing (', tenant1_id, ')') AS log_message;
    
    -- test_user 属于"测试公司"
    UPDATE `users` SET `tenant_id` = tenant2_id, `role` = 'user' WHERE `username` = 'test_user' AND `tenant_id` IS NULL;
    SELECT CONCAT('Updated test_user to tenant: test_company (', tenant2_id, ')') AS log_message;
    
    -- ========================================
    -- 9. 更新现有数据的 tenant_id
    -- ========================================
    -- 所有现有数据都属于"任我行"
    UPDATE `dbconnection` SET `tenant_id` = tenant1_id WHERE `tenant_id` IS NULL;
    SELECT CONCAT('Updated ', ROW_COUNT(), ' dbconnection records to tenant: renwoxing') AS log_message;
    
    UPDATE `llm_configuration` SET `tenant_id` = tenant1_id WHERE `tenant_id` IS NULL;
    SELECT CONCAT('Updated ', ROW_COUNT(), ' llm_configuration records to tenant: renwoxing') AS log_message;
    
    UPDATE `agent_profile` SET `tenant_id` = tenant1_id WHERE `tenant_id` IS NULL AND `is_system` = FALSE;
    SELECT CONCAT('Updated ', ROW_COUNT(), ' agent_profile records to tenant: renwoxing') AS log_message;
    
    SELECT 'Migration completed successfully!' AS final_status;
END//

DELIMITER ;

-- 执行迁移
CALL add_multi_tenant_support();

-- 清理存储过程
DROP PROCEDURE IF EXISTS add_multi_tenant_support;

-- 显示结果
SELECT '=== Tenants ===' AS info;
SELECT id, name, display_name FROM tenants;

SELECT '=== Users ===' AS info;
SELECT u.id, u.username, u.role, u.tenant_id, t.display_name AS tenant_name 
FROM users u LEFT JOIN tenants t ON u.tenant_id = t.id;

SELECT '=== Data Summary ===' AS info;
SELECT 'dbconnection' AS TableName, COUNT(*) AS TotalRows, COUNT(tenant_id) AS WithTenantId FROM dbconnection
UNION ALL
SELECT 'llm_configuration', COUNT(*), COUNT(tenant_id) FROM llm_configuration
UNION ALL
SELECT 'agent_profile', COUNT(*), COUNT(tenant_id) FROM agent_profile;
