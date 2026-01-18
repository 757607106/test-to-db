-- MySQL 初始化脚本
-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS chatdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE chatdb;

-- 设置时区
SET time_zone = '+08:00';

-- 创建用户（如果不存在）
-- CREATE USER IF NOT EXISTS 'chatdb_user'@'%' IDENTIFIED BY 'chatdb_password';
-- GRANT ALL PRIVILEGES ON chatdb.* TO 'chatdb_user'@'%';
-- FLUSH PRIVILEGES;

-- 注意：实际的表结构由 Alembic 迁移创建
-- 这个脚本只是确保数据库存在并配置正确
