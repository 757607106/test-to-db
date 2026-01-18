-- 清理硬编码的 Sample Database 连接
-- 使用方法: mysql -u root -pmysql chatdb < cleanup_sample_db.sql

USE chatdb;

-- 显示将要删除的连接
SELECT '当前 Sample Database 连接信息:' as Info;
SELECT id, name, db_type, host, port, database_name, created_at 
FROM db_connection 
WHERE name = 'Sample Database';

-- 删除 Sample Database 连接
DELETE FROM db_connection WHERE name = 'Sample Database';

-- 显示删除结果
SELECT CONCAT('✅ 已删除 ', ROW_COUNT(), ' 个连接') as Result;

-- 显示当前所有连接
SELECT '当前所有数据库连接:' as Info;
SELECT id, name, db_type, host, port, database_name 
FROM db_connection 
ORDER BY created_at DESC;
