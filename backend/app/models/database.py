"""
数据库模型定义
每个类对应数据库中的一张表
"""
from sqlalchemy import (
    Column, Integer, String, Text, Float, Date, DateTime,
    ForeignKey, Boolean, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import enum


# 创建所有模型的基类
Base = declarative_base()


class UserRole(str, enum.Enum):
    """用户角色枚举"""
    ADMIN = "admin"      # 管理员：全部权限
    USER = "user"        # 普通用户：录入、查看、下载、修改自己的、备忘录


class ContractType(str, enum.Enum):
    """合同类型枚举"""
    PROCUREMENT = "采购"
    SALE = "销售"
    OTHER = "其他"


class ContractStatus(str, enum.Enum):
    """合同状态枚举"""
    ACTIVE = "有效"
    VOID = "作废"


# ==================== 用户表 ====================
class User(Base):
    """
    用户表
    存储系统用户信息
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False, comment="角色")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    
    # 登录安全相关
    failed_attempts = Column(Integer, default=0, nullable=False, comment="连续登录失败次数")
    locked_until = Column(DateTime, nullable=True, comment="账户锁定截止时间")
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间")

    # 关联：用户创建的合同
    # 注意：不设置 cascade delete，删除用户时合同保留（合同属于公司资产）
    contracts = relationship("Contract", back_populates="creator")


# ==================== 我方公司表 ====================
class Company(Base):
    """
    我方公司表
    管理员可在后台管理的公司列表
    """
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False, comment="公司名称")
    keywords = Column(String(500), nullable=True, comment="识别关键词，逗号分隔")
    sort_order = Column(Integer, default=0, comment="排序顺序")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")

    # 关联：公司下的合同
    contracts = relationship("Contract", back_populates="company")


# ==================== 合同主表 ====================
class Contract(Base):
    """
    合同主表
    存储合同的核心信息
    """
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)

    # 合同基本信息
    contract_no = Column(String(100), index=True, nullable=False, comment="合同编号")
    contract_name = Column(String(500), nullable=False, comment="合同名称")
    contract_type = Column(SQLEnum(ContractType), nullable=False, comment="合同类型")
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, comment="我方公司ID")
    counterparty = Column(String(500), nullable=False, comment="对方公司名称")

    # 日期相关
    submit_date = Column(Date, nullable=False, default=datetime.now, comment="合同提交日期")
    valid_until = Column(Date, nullable=True, comment="有效期至")

    # 人员信息
    department = Column(String(200), nullable=False, comment="所属部门")
    handler = Column(String(100), nullable=True, comment="经办人")

    # 金额和份数
    amount = Column(String(100), nullable=True, comment="合同金额")
    paper_copies = Column(String(50), nullable=True, comment="纸质份数")

    # 其他
    remarks = Column(Text, nullable=True, comment="备注")
    memo = Column(Text, nullable=True, comment="备忘录（随时可改）")
    status = Column(SQLEnum(ContractStatus), default=ContractStatus.ACTIVE, nullable=False, comment="合同状态：有效/作废")

    # 审计字段
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="创建人ID")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间")

    # 关联
    creator = relationship("User", back_populates="contracts")
    company = relationship("Company", back_populates="contracts")
    attachments = relationship("Attachment", back_populates="contract", cascade="all, delete-orphan")


# ==================== 附件表 ====================
class Attachment(Base):
    """
    附件表
    一条合同可以有多条附件（一对多关系）
    """
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, comment="关联合同ID")
    file_name = Column(String(255), nullable=False, comment="原始文件名")
    stored_name = Column(String(255), nullable=False, comment="存储文件名（防重名）")
    file_path = Column(String(500), nullable=False, comment="文件存储路径")
    file_type = Column(String(20), nullable=False, comment="文件类型：pdf/image/word")
    file_size = Column(Integer, nullable=True, comment="文件大小（字节）")
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False, comment="上传人ID")
    uploaded_at = Column(DateTime, server_default=func.now(), nullable=False, comment="上传时间")

    # 关联
    contract = relationship("Contract", back_populates="attachments")
    uploader = relationship("User")
