-- =====================================================
-- 合同归档系统 - 数据库初始化脚本
-- 首次启动时自动执行，创建所有表和初始数据
-- =====================================================

-- 启用 UUID 生成
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- 用户表
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
    is_active BOOLEAN DEFAULT TRUE,
    failed_attempts INTEGER DEFAULT 0 NOT NULL,  -- 连续登录失败次数
    locked_until TIMESTAMP,                        -- 账户锁定截止时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 我方公司配置表（管理员可在后台管理）
-- =====================================================
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    short_name VARCHAR(100),
    keywords TEXT,  -- 用于OCR识别的关键词，逗号分隔，如"济南,JN"
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 合同类型配置表
-- =====================================================
CREATE TABLE IF NOT EXISTS contract_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 合同主表
-- =====================================================
CREATE TABLE IF NOT EXISTS contracts (
    id SERIAL PRIMARY KEY,
    contract_no VARCHAR(100) NOT NULL,           -- 合同编号（云之家审批编号）
    contract_name VARCHAR(500) NOT NULL,         -- 合同名称
    contract_type VARCHAR(50) NOT NULL,         -- 采购/销售/其他
    our_company VARCHAR(200),                    -- 我方公司名称
    counterparty VARCHAR(200) NOT NULL,         -- 对方公司名称
    submit_date DATE,                            -- 合同提交时间
    valid_until DATE,                            -- 有效期
    department VARCHAR(100),                     -- 所属部门
    handler VARCHAR(100),                        -- 经办人
    amount DECIMAL(15, 2),                      -- 合同金额
    paper_copies VARCHAR(50),                    -- 纸质份数
    remarks TEXT,                                -- 备注
    memo TEXT,                                   -- 备忘录（随时可改）
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引加速搜索
CREATE INDEX IF NOT EXISTS idx_contracts_no ON contracts(contract_no);
CREATE INDEX IF NOT EXISTS idx_contracts_name ON contracts(contract_name);
CREATE INDEX IF NOT EXISTS idx_contracts_type ON contracts(contract_type);
CREATE INDEX IF NOT EXISTS idx_contracts_company ON contracts(our_company);
CREATE INDEX IF NOT EXISTS idx_contracts_counterparty ON contracts(counterparty);
CREATE INDEX IF NOT EXISTS idx_contracts_department ON contracts(department);
CREATE INDEX IF NOT EXISTS idx_contracts_submit_date ON contracts(submit_date);
CREATE INDEX IF NOT EXISTS idx_contracts_created_by ON contracts(created_by);

-- =====================================================
-- 附件表（一对多：一个合同多个附件）
-- =====================================================
CREATE TABLE IF NOT EXISTS attachments (
    id SERIAL PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,             -- 原始文件名
    file_path VARCHAR(500) NOT NULL,             -- 服务器存储路径
    file_type VARCHAR(20) NOT NULL,              -- pdf/image/word
    file_size BIGINT,                            -- 文件大小（字节）
    uploaded_by INTEGER REFERENCES users(id),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attachments_contract ON attachments(contract_id);

-- =====================================================
-- 初始化数据
-- =====================================================

-- 插入默认管理员账号（密码：admin123，生产环境请立即修改）
-- 密码哈希：scrypt:32768:8:1$=argon2id$v19$...
INSERT INTO users (username, password_hash, display_name, role)
VALUES ('admin', 'argon2$argon2id$v=19$m=65536,t=3,p=4$VGF5UGFzc3dvcmQxMjM0NTY$hKXQFhJRNm5dR8qT9Y3vLQmD3yXzJGvkWP7cE6hH8aA', '系统管理员', 'admin')
ON CONFLICT (username) DO NOTHING;

INSERT INTO users (username, password_hash, display_name, role)
VALUES ('test', 'argon2$argon2id$v=19$m=65536,t=3,p=4$VGF5UGFzc3dvcmQxMjM0NTY$hKXQFhJRNm5dR8qT9Y3vLQmD3yXzJGvkWP7cE6hH8aA', '测试用户', 'user')
ON CONFLICT (username) DO NOTHING;

-- 插入合同类型（固定三种）
INSERT INTO contract_types (name, sort_order) VALUES 
    ('采购', 1),
    ('销售', 2),
    ('其他', 3)
ON CONFLICT DO NOTHING;

-- 插入公司列表（OCR识别关键词用于自动匹配）
-- ⚠️ 请根据实际公司信息修改以下示例数据
INSERT INTO companies (name, short_name, keywords, sort_order) VALUES 
    ('示例科技有限公司', '科技', '示例,科技', 1),
    ('示例贸易有限公司', '贸易', '示例,贸易', 2),
    ('示例咨询有限公司', '咨询', '示例,咨询', 3)
ON CONFLICT DO NOTHING;

-- 显示初始化结果
SELECT '数据库初始化完成！' AS status;
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
