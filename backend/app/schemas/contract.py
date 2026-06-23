"""
合同相关的数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


# ==================== 枚举定义 ====================
class ContractTypeEnum(str, Enum):
    PROCUREMENT = "采购"
    SALE = "销售"
    OTHER = "其他"


class ContractStatusEnum(str, Enum):
    ACTIVE = "有效"
    VOID = "作废"


# ==================== 我方公司 ====================
class CompanyBase(BaseModel):
    """公司基础信息"""
    name: str = Field(..., max_length=200)
    keywords: Optional[str] = Field(None, max_length=500, description="识别关键词，逗号分隔")


class CompanyCreate(CompanyBase):
    """创建公司"""
    pass


class CompanyResponse(CompanyBase):
    """公司响应"""
    id: int
    sort_order: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 合同 ====================
class ContractBase(BaseModel):
    """合同基础字段"""
    contract_no: str = Field(..., max_length=100, description="合同编号")
    contract_name: str = Field(..., max_length=500, description="合同名称")
    contract_type: ContractTypeEnum = Field(..., description="合同类型")
    counterparty: str = Field(..., max_length=500, description="对方公司")
    submit_date: date = Field(..., description="提交日期")
    valid_until: Optional[date] = Field(None, description="有效期至")
    department: str = Field(..., max_length=200, description="部门")
    handler: Optional[str] = Field(None, max_length=100, description="经办人")
    amount: Optional[str] = Field(None, max_length=100, description="金额")
    paper_copies: Optional[str] = Field(None, max_length=50, description="纸质份数")
    remarks: Optional[str] = Field(None, description="备注")
    memo: Optional[str] = Field(None, description="备忘录")


class ContractCreate(ContractBase):
    """创建合同"""
    company_id: Optional[int] = Field(None, description="我方公司ID")
    status: Optional[str] = Field("有效", description="合同状态：有效/作废")


class ContractUpdate(BaseModel):
    """更新合同（排除备忘录和创建人）"""
    contract_no: Optional[str] = Field(None, max_length=100)
    contract_name: Optional[str] = Field(None, max_length=500)
    contract_type: Optional[ContractTypeEnum] = None
    counterparty: Optional[str] = Field(None, max_length=500)
    submit_date: Optional[date] = None
    valid_until: Optional[date] = None
    department: Optional[str] = Field(None, max_length=200)
    handler: Optional[str] = Field(None, max_length=100)
    amount: Optional[str] = Field(None, max_length=100)
    paper_copies: Optional[str] = Field(None, max_length=50)
    remarks: Optional[str] = None
    company_id: Optional[int] = None
    status: Optional[str] = None


class ContractMemoUpdate(BaseModel):
    """仅更新备忘录（无需权限校验）"""
    memo: str


class ContractStatusUpdate(BaseModel):
    """仅更新合同状态（管理员专用）"""
    status: str


class ContractResponse(ContractBase):
    """合同响应"""
    id: int
    company_id: Optional[int]
    company_name: Optional[str] = None
    created_by: int
    creator_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    status: str = "有效"
    attachments: List["AttachmentResponse"] = []

    class Config:
        from_attributes = True


class ContractListResponse(BaseModel):
    """合同列表响应（不含附件详情，含附件数量）"""
    id: int
    contract_no: str
    contract_name: str
    contract_type: str
    company_name: Optional[str]
    counterparty: str
    submit_date: date
    amount: Optional[str]
    department: str
    handler: Optional[str]
    memo: Optional[str]
    attachment_count: int = 0
    created_at: datetime
    creator_name: Optional[str] = None
    status: str = "有效"

    class Config:
        from_attributes = True


class PaginatedContractListResponse(BaseModel):
    """合同列表分页响应"""
    items: list["ContractListResponse"]
    total: int
    page: int
    page_size: int


# ==================== 附件 ====================
class AttachmentResponse(BaseModel):
    """附件响应"""
    id: int
    file_name: str
    file_type: str
    file_size: Optional[int]
    uploaded_at: datetime
    uploaded_by: int
    uploader_name: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== 查询参数 ====================
class ContractSearchParams(BaseModel):
    """合同查询参数"""
    keyword: Optional[str] = Field(None, description="关键词搜索")
    contract_type: Optional[str] = Field(None, description="合同类型")
    company_id: Optional[int] = Field(None, description="我方公司")
    counterparty: Optional[str] = Field(None, description="对方公司")
    department: Optional[str] = Field(None, description="部门")
    submit_date_from: Optional[date] = Field(None, description="提交日期起")
    submit_date_to: Optional[date] = Field(None, description="提交日期止")
    amount_min: Optional[float] = Field(None, description="最小金额")
    amount_max: Optional[float] = Field(None, description="最大金额")


# ==================== OCR 结果 ====================
class OCRResult(BaseModel):
    """OCR 识别结果"""
    contract_no: Optional[str] = None
    contract_name: Optional[str] = None
    counterparty: Optional[str] = None
    amount: Optional[str] = None
    date: Optional[str] = None
    raw_text: str = Field(..., description="原始识别文本")
    # v3.1 新增：我方公司匹配
    matched_company_id: Optional[int] = Field(None, description="匹配到的我方公司ID")
    matched_company_name: Optional[str] = Field(None, description="匹配到的我方公司名称")
    counterparty_candidates: Optional[List[str]] = Field(None, description="候选对方公司列表（OCR中未匹配到我方公司的公司名）")
    # v3.2 新增：OCR 管道诊断信息
    diagnostics: Optional[dict] = Field(None, description="OCR 管道各层诊断信息")
    # v3.3 新增：AI 增强标识
    ai_enhanced: Optional[bool] = Field(None, description="是否使用了 AI 增强识别")
    # v3.4 新增：AI 原始提取结果（用于前端诊断展示）
    ai_raw: Optional[dict] = Field(None, description="AI 提取的原始字段值")
    # v3.5 新增：AI 调用模式（full=全量覆盖, fallback=兜底补充, none=未启用）
    ai_mode: Optional[str] = Field(None, description="AI 调用模式: full / fallback / none")


# 前向引用（解决循环依赖）
ContractResponse.model_rebuild()
