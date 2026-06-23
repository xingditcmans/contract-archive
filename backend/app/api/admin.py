"""
管理员功能 API
备份与恢复、系统管理、AI 配置
"""
import logging
import os
import json
import zipfile
import io
import shutil
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.core.database import get_db
from app.core.security import get_current_admin
from app.core.config import settings
from app.models.database import Contract, Attachment, User, Company, ContractType
from app.utils.file_security import safe_save_file

router = APIRouter(prefix="/api/admin", tags=["管理员功能"])
audit_logger = logging.getLogger("audit")


def _safe_detail(msg: str) -> str:
    """生产环境返回通用错误消息，防止泄露内部异常详情"""
    if settings.is_production:
        return "操作失败，请稍后重试"
    return msg


# ==================== 备份导出 ====================

@router.post("/backup")
async def backup_contracts(
    request: Request,
    year: Optional[int] = Query(None, description="筛选年份，如 2024"),
    contract_type: Optional[str] = Query(None, description="合同类型：采购/销售/其他"),
    all: bool = Query(False, description="导出全部（忽略年份和类型筛选）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    备份合同数据为 ZIP 压缩包

    ZIP 结构：
    ├── manifest.json        # 备份元数据
    ├── contracts.json       # 完整合同数据（含附件映射）
    └── attachments/         # 附件文件
        └── {合同编号}/
            └── xxx.pdf

    筛选条件：
    - 不传参数 + all=false：默认导出全部
    - year=2024：只导出提交日期在2024年的合同
    - contract_type=采购：只导出指定类型的合同
    - 二者组合使用
    """
    # 构建查询
    query = db.query(Contract)

    if not all:
        if year:
            query = query.filter(extract('year', Contract.submit_date) == year)
        if contract_type:
            try:
                ct = ContractType(contract_type)
                query = query.filter(Contract.contract_type == ct)
            except ValueError:
                valid_types = [t.value for t in ContractType]
                raise HTTPException(
                    status_code=400,
                    detail=f"无效的合同类型 '{contract_type}'，可选值: {', '.join(valid_types)}"
                )

    contracts = query.order_by(Contract.submit_date.desc(), Contract.id.asc()).all()

    if not contracts:
        raise HTTPException(status_code=404, detail="没有符合条件的合同数据")

    # 构建内存中的 ZIP 文件
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. 收集合同数据和附件路径
        contracts_data = []
        total_attachments = 0
        skipped_files = []

        for contract in contracts:
            # 获取创建者信息
            creator = db.query(User).filter(User.id == contract.created_by).first()
            company = db.query(Company).filter(Company.id == contract.company_id).first()

            # 获取附件列表
            attachments = db.query(Attachment).filter(
                Attachment.contract_id == contract.id
            ).all()

            contract_attachments = []
            safe_contract_no = _safe_folder_name(contract.contract_no)

            for att in attachments:
                total_attachments += 1
                # 附件在 ZIP 中的路径
                zip_att_path = f"attachments/{safe_contract_no}/{att.file_name}"

                # 将附件文件添加到 ZIP
                if os.path.exists(att.file_path):
                    try:
                        zf.write(att.file_path, zip_att_path)
                    except Exception as e:
                        skipped_files.append({
                            "contract_no": contract.contract_no,
                            "file_name": att.file_name,
                            "reason": str(e)
                        })
                        continue
                else:
                    skipped_files.append({
                        "contract_no": contract.contract_no,
                        "file_name": att.file_name,
                        "reason": "文件已丢失"
                    })
                    continue

                contract_attachments.append({
                    "file_name": att.file_name,
                    "file_path": zip_att_path,
                    "file_type": att.file_type,
                    "file_size": att.file_size,
                    "uploaded_at": att.uploaded_at.isoformat() if att.uploaded_at else None,
                })

            contracts_data.append({
                "contract_no": contract.contract_no,
                "contract_name": contract.contract_name,
                "contract_type": contract.contract_type.value,
                "company_name": company.name if company else None,
                "counterparty": contract.counterparty,
                "submit_date": contract.submit_date.isoformat() if contract.submit_date else None,
                "valid_until": contract.valid_until.isoformat() if contract.valid_until else None,
                "department": contract.department,
                "handler": contract.handler,
                "amount": contract.amount,
                "paper_copies": contract.paper_copies,
                "remarks": contract.remarks,
                "memo": contract.memo,
                "created_at": contract.created_at.isoformat() if contract.created_at else None,
                "updated_at": contract.updated_at.isoformat() if contract.updated_at else None,
                "creator_name": creator.username if creator else None,
                "attachments": contract_attachments,
            })

        # 2. 写入 manifest.json
        manifest = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "total_contracts": len(contracts_data),
            "total_attachments": total_attachments - len(skipped_files),
            "skipped_files": skipped_files if skipped_files else [],
            "filter": {
                "year": year,
                "contract_type": contract_type,
                "all": all,
            },
            "exported_by": current_user.username,
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        # 3. 写入 contracts.json
        zf.writestr(
            "contracts.json",
            json.dumps({"contracts": contracts_data}, ensure_ascii=False, indent=2)
        )

    # 审计日志
    audit_logger.warning({
        "action": "BACKUP_EXPORTED",
        "total_contracts": len(contracts_data),
        "total_attachments": total_attachments,
        "skipped_files": len(skipped_files),
        "filter": {"year": year, "contract_type": contract_type, "all": all},
        "operator": current_user.username,
        "ip": request.client.host if request.client else "unknown",
    })

    # 返回 ZIP 文件
    zip_buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"contract_backup_{timestamp}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Backup-Contracts": str(len(contracts_data)),
            "X-Backup-Attachments": str(total_attachments - len(skipped_files)),
        }
    )


# ==================== 恢复导入 ====================

@router.post("/restore")
async def restore_contracts(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    从备份 ZIP 恢复合同数据（覆盖模式）

    流程：
    1. 解析 ZIP 中的 manifest.json 和 contracts.json
    2. 逐条处理：合同编号已存在 → 覆盖更新（含附件替换）；新合同 → 直接创建
    3. 从 ZIP 中提取附件并保存到 uploads 目录
    4. 返回恢复汇总（created/overwritten/attachments_restored）
    """
    # 验证文件类型
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的备份文件")

    # 读取 ZIP 到内存
    zip_content = await file.read()
    zip_buffer = io.BytesIO(zip_content)

    try:
        zf = zipfile.ZipFile(zip_buffer, 'r')
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="无效的 ZIP 文件，请上传正确的备份文件")

    # 验证 ZIP 结构
    file_list = zf.namelist()
    if "contracts.json" not in file_list:
        raise HTTPException(status_code=400, detail="备份文件缺少 contracts.json，格式不正确")

    # 1. 读取 contracts.json
    contracts_raw = json.loads(zf.read("contracts.json").decode("utf-8"))
    contracts_data = contracts_raw.get("contracts", [])

    # 2. 可选：读取 manifest
    manifest = {}
    if "manifest.json" in file_list:
        try:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        except Exception:
            pass

    # 3. 逐条导入（覆盖模式）
    result = {
        "total": len(contracts_data),
        "created": 0,
        "overwritten": 0,
        "errors": [],
        "attachments_restored": 0,
        "attachments_skipped": 0,
    }

    for item in contracts_data:
        contract_no = item.get("contract_no", "")

        try:
            # 解析日期
            submit_date = None
            if item.get("submit_date"):
                try:
                    submit_date = datetime.fromisoformat(item["submit_date"]).date()
                except Exception:
                    submit_date = date.today()

            valid_until = None
            if item.get("valid_until"):
                try:
                    valid_until = datetime.fromisoformat(item["valid_until"]).date()
                except Exception:
                    pass

            # 合同类型标准化
            contract_type_str = item.get("contract_type", "其他")
            try:
                contract_type = ContractType(contract_type_str)
            except ValueError:
                contract_type = ContractType.OTHER

            # 检查合同编号是否已存在
            existing = db.query(Contract).filter(
                Contract.contract_no == contract_no
            ).first()

            if existing:
                # === 覆盖模式：更新已有合同 ===
                existing.contract_name = item.get("contract_name", existing.contract_name)
                existing.contract_type = contract_type
                existing.counterparty = item.get("counterparty", existing.counterparty)
                existing.submit_date = submit_date or existing.submit_date
                existing.valid_until = valid_until  # 可为 None
                existing.department = item.get("department", existing.department)
                existing.handler = item.get("handler", existing.handler)
                existing.amount = item.get("amount", existing.amount)
                existing.paper_copies = item.get("paper_copies", existing.paper_copies)
                existing.remarks = item.get("remarks", existing.remarks)
                existing.memo = item.get("memo", existing.memo)

                # 删除旧附件（DB记录 + 磁盘文件）
                old_attachments = db.query(Attachment).filter(
                    Attachment.contract_id == existing.id
                ).all()
                for old_att in old_attachments:
                    # 删除磁盘文件
                    if os.path.exists(old_att.file_path):
                        try:
                            os.remove(old_att.file_path)
                        except OSError:
                            pass
                    db.delete(old_att)
                db.flush()

                target_contract = existing
                result["overwritten"] += 1
            else:
                # === 新建合同 ===
                contract = Contract(
                    contract_no=contract_no,
                    contract_name=item.get("contract_name", ""),
                    contract_type=contract_type,
                    counterparty=item.get("counterparty", "未知"),
                    submit_date=submit_date or date.today(),
                    valid_until=valid_until,
                    department=item.get("department", "未知部门"),
                    handler=item.get("handler"),
                    amount=item.get("amount"),
                    paper_copies=item.get("paper_copies"),
                    remarks=item.get("remarks"),
                    memo=item.get("memo"),
                    created_by=current_user.id,
                )
                db.add(contract)
                db.flush()
                target_contract = contract
                result["created"] += 1

            # 恢复附件（新增和覆盖都走这段）
            attachments_list = item.get("attachments", [])
            for att_item in attachments_list:
                zip_att_path = att_item.get("file_path", "")
                file_name = att_item.get("file_name", "")

                if not zip_att_path or zip_att_path not in file_list:
                    result["attachments_skipped"] += 1
                    result["errors"].append({
                        "contract_no": contract_no,
                        "file_name": file_name,
                        "type": "attachment_missing",
                        "message": f"附件 {file_name} 在备份中不存在，跳过",
                    })
                    continue

                try:
                    # 从 ZIP 读取附件内容
                    file_content = zf.read(zip_att_path)

                    # 保存到 uploads 目录
                    saved_path, saved_name, file_hash = safe_save_file(
                        content=file_content,
                        upload_dir=settings.UPLOAD_DIR,
                        original_filename=file_name,
                        max_size=settings.MAX_FILE_SIZE,
                        contract_no=contract_no,
                    )

                    # 确定文件类型
                    ext = os.path.splitext(file_name)[1].lower()
                    if ext == ".pdf":
                        ft = "pdf"
                    elif ext in [".jpg", ".jpeg", ".png"]:
                        ft = "image"
                    else:
                        ft = "word"

                    # 创建附件记录
                    attachment = Attachment(
                        contract_id=target_contract.id,
                        file_name=saved_name,
                        stored_name=os.path.basename(saved_path),
                        file_path=saved_path,
                        file_type=ft,
                        file_size=len(file_content),
                        uploaded_by=current_user.id,
                    )
                    db.add(attachment)
                    result["attachments_restored"] += 1

                except HTTPException:
                    raise
                except Exception as e:
                    result["attachments_skipped"] += 1
                    result["errors"].append({
                        "contract_no": contract_no,
                        "file_name": file_name,
                        "type": "attachment_save_failed",
                        "message": _safe_detail(f"附件 {file_name} 保存失败: {str(e)}"),
                    })

        except Exception as e:
            db.rollback()
            result["errors"].append({
                "contract_no": contract_no,
                "contract_name": item.get("contract_name", ""),
                "type": "create_failed",
                "message": _safe_detail(f"合同 {contract_no} 处理失败: {str(e)}"),
            })
            continue

    db.commit()

    # 审计日志
    audit_logger.warning({
        "action": "BACKUP_RESTORED",
        "total": result["total"],
        "created": result["created"],
        "overwritten": result["overwritten"],
        "attachments_restored": result["attachments_restored"],
        "attachments_skipped": result["attachments_skipped"],
        "error_count": len(result["errors"]),
        "operator": current_user.username,
        "ip": request.client.host if request.client else "unknown",
    })

    return result


# ==================== 辅助函数 ====================

def _safe_folder_name(name: str) -> str:
    """
    将合同编号转为安全的文件夹名
    移除 Windows/Linux 文件系统不允许的字符
    """
    unsafe_chars = r'<>:"/\|?*'
    for ch in unsafe_chars:
        name = name.replace(ch, '_')
    # 去掉前后空白和点
    name = name.strip('. ')
    return name or "unknown"


# ==================== AI 配置管理 ====================

from pydantic import BaseModel as PydanticBaseModel
from app.utils.ai_extractor import get_ai_config, update_ai_config, PROVIDER_PRESETS, HAS_HTTPX


class AIConfigUpdate(PydanticBaseModel):
    """AI 配置更新请求"""
    enabled: Optional[bool] = None
    provider: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    timeout_seconds: Optional[int] = None
    fallback_only: Optional[bool] = None


@router.get("/ai-config")
async def get_ai_settings(
    current_user: User = Depends(get_current_admin)
):
    """
    获取当前 AI 配置（仅管理员）

    返回：
    - 当前配置
    - 预设提供商列表
    - httpx 是否可用
    """
    config = get_ai_config()
    # 脱敏 API Key
    if config.get("api_key"):
        key = config["api_key"]
        config["api_key_masked"] = key[:8] + "****" + key[-4:] if len(key) > 12 else "****"
    else:
        config["api_key_masked"] = ""
    return config


@router.put("/ai-config")
async def update_ai_settings(
    body: AIConfigUpdate,
    current_user: User = Depends(get_current_admin)
):
    """
    更新 AI 配置（仅管理员）

    支持部分更新：只传需要修改的字段即可
    """
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="没有提供任何更新字段")

    # 验证 provider 切换时自动填充预设
    if "provider" in updates and updates["provider"] in PROVIDER_PRESETS:
        preset = PROVIDER_PRESETS[updates["provider"]]
        if not updates.get("api_url"):
            updates["api_url"] = preset["api_url"]
        if not updates.get("model"):
            updates["model"] = preset["default_model"]

    result = update_ai_config(updates)

    # 审计日志
    audit_logger.warning({
        "action": "AI_CONFIG_UPDATED",
        "fields": list(updates.keys()),
        "operator": current_user.username,
    })

    return {"message": "AI 配置已更新", "config": result}


@router.post("/ai-test")
async def test_ai_connection(
    current_user: User = Depends(get_current_admin)
):
    """
    测试 AI 连接（仅管理员）

    发送一个简单的测试请求验证 API 配置是否正确
    """
    if not HAS_HTTPX:
        raise HTTPException(status_code=500, detail="httpx 未安装，请执行: pip install httpx")

    config = get_ai_config()

    if not config.get("enabled"):
        raise HTTPException(status_code=400, detail="AI 功能未启用")

    api_url = config.get("api_url", "")
    api_key = config.get("api_key", "")
    model = config.get("model", "")

    if not api_url or not model:
        raise HTTPException(status_code=400, detail="AI 配置不完整，请填写 API 地址和模型名称")

    import httpx

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(
            base_url=api_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(15.0),
        ) as client:
            start = __import__("time").time()
            response = await client.post(
                "/chat/completions",
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": "请回复一个单词: OK"},
                    ],
                    "max_tokens": 10,
                },
            )
            elapsed = __import__("time").time() - start

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return {
                    "success": True,
                    "message": f"连接成功！模型回复: {content}",
                    "elapsed_seconds": round(elapsed, 2),
                    "model": model,
                    "tokens": usage.get("total_tokens", 0),
                }
            else:
                return {
                    "success": False,
                    "message": f"API 返回错误 ({response.status_code})",
                    "detail": response.text[:500],
                    "elapsed_seconds": round(elapsed, 2),
                }

    except httpx.ConnectError:
        return {
            "success": False,
            "message": "无法连接到 API 服务器，请检查 API 地址是否正确",
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "连接超时，请检查网络或增加超时时间",
        }
    except Exception as e:
        return {
            "success": False,
            "message": _safe_detail(f"连接失败: {type(e).__name__}: {str(e)[:300]}"),
        }
