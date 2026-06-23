"""
文件安全处理工具
防止恶意文件上传和路径穿越攻击
"""
import os
import hashlib

# 文件类型检测通过 FILE_SIGNATURES 魔数字典实现，无需 python-magic
from typing import Tuple, Optional
from fastapi import HTTPException

# 延迟导入设置以避免循环依赖
SETTINGS = None


def _get_settings():
    global SETTINGS
    if SETTINGS is None:
        from app.core.config import settings as s
        SETTINGS = s
    return SETTINGS


def _safe_detail(msg: str) -> str:
    """生产环境返回通用错误消息，防止泄露内部异常详情"""
    if _get_settings().is_production:
        return "操作失败，请稍后重试"
    return msg


# 文件魔数（文件头）映射 - 用于验证文件真实类型
FILE_SIGNATURES = {
    '.pdf': [b'%PDF'],  # PDF文件以 %PDF 开头
    '.jpg': [b'\xff\xd8\xff'],  # JPEG
    '.jpeg': [b'\xff\xd8\xff'],
    '.png': [b'\x89PNG'],  # PNG
    '.doc': [b'\xd0\xcf\x11\xe0'],  # Office旧版格式
    '.docx': [b'PK\x03\x04'],  # Office新版格式（ZIP）
}

# MIME类型映射
MIME_TYPES = {
    '.pdf': 'application/pdf',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，防止路径穿越攻击
    
    攻击示例：
    - "../../../etc/passwd" -> "passwd"
    - "..\\..\\windows\\system32\\config\\sam" -> "sam"
    - "..%2F..%2F..%2Fetc%2Fpasswd" -> "passwd"
    """
    # 移除路径中的危险字符
    filename = os.path.basename(filename)  # 只取文件名部分
    filename = filename.replace("..", "")  # 移除双点
    filename = filename.replace("/", "")  # 移除正斜杠
    filename = filename.replace("\\", "")  # 移除反斜杠
    filename = filename.replace("\x00", "")  # 移除空字节
    
    # 限制长度
    if len(filename) > 255:
        filename = filename[:255]
    
    return filename or "unnamed_file"


def verify_file_content(file_content: bytes, expected_ext: str) -> Tuple[bool, str]:
    """
    验证文件内容是否与声明的扩展名匹配
    
    返回：(验证是否通过, 错误信息)
    """
    if expected_ext not in FILE_SIGNATURES:
        return False, f"不支持的文件类型: {expected_ext}"
    
    # 检查文件魔数
    signatures = FILE_SIGNATURES[expected_ext]
    for sig in signatures:
        if file_content[:len(sig)] == sig:
            return True, "OK"
    
    return False, f"文件内容与扩展名不匹配，可能被伪装"


def validate_file_size(content: bytes, max_size: int) -> Tuple[bool, str]:
    """
    验证文件大小
    
    返回：(验证是否通过, 错误信息)
    """
    size = len(content)
    
    if size == 0:
        return False, "文件不能为空"
    
    if size > max_size:
        max_mb = max_size / (1024 * 1024)
        actual_mb = size / (1024 * 1024)
        return False, f"文件大小 ({actual_mb:.1f}MB) 超过限制 ({max_mb:.0f}MB)"
    
    return True, "OK"


def calculate_file_hash(content: bytes) -> str:
    """
    计算文件SHA256哈希，用于审计追踪
    """
    return hashlib.sha256(content).hexdigest()


def safe_save_file(
    content: bytes,
    upload_dir: str,
    original_filename: str,
    max_size: int = 50 * 1024 * 1024,
    contract_no: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    安全地保存上传的文件
    
    1. 验证文件大小
    2. 验证文件内容
    3. 有合同编号 → 存到 {upload_dir}/{合同编号}/原始文件名.ext（容灾可读）
       无合同编号 → 降级为随机文件名（兼容旧逻辑）
    4. 安全保存
    
    返回：(存储路径, 原始文件名, 文件哈希)
    
    异常：
    - 文件大小超标
    - 文件内容验证失败
    - 存储失败
    """
    import uuid
    
    # 获取文件扩展名
    ext = os.path.splitext(original_filename)[1].lower()
    
    # 1. 验证文件大小
    size_ok, size_msg = validate_file_size(content, max_size)
    if not size_ok:
        raise HTTPException(status_code=400, detail=size_msg)
    
    # 2. 验证文件内容（魔数检测）
    if ext in FILE_SIGNATURES:
        content_ok, content_msg = verify_file_content(content, ext)
        if not content_ok:
            raise HTTPException(
                status_code=400, 
                detail=f"安全验证失败：{content_msg}"
            )
    
    # 3. 清理原始文件名
    safe_original_name = sanitize_filename(original_filename)
    
    # 4. 决定存储路径
    if contract_no:
        # 有合同编号：存储到子目录，使用原始文件名（容灾友好）
        safe_contract_dir = sanitize_filename(contract_no)
        target_dir = os.path.join(upload_dir, safe_contract_dir)
        os.makedirs(target_dir, exist_ok=True)
        
        # 处理同合同内文件名冲突（如多个附件都叫"合同.pdf"）
        stored_name = safe_original_name
        if not stored_name:
            import time
            stored_name = f"{int(time.time() * 1000)}{ext}"
        
        candidate_path = os.path.join(target_dir, stored_name)
        counter = 1
        base, file_ext = os.path.splitext(stored_name)
        while os.path.exists(candidate_path):
            stored_name = f"{base} ({counter}){file_ext}"
            candidate_path = os.path.join(target_dir, stored_name)
            counter += 1
        
        safe_path = os.path.abspath(candidate_path)
    else:
        # 无合同编号：降级为随机文件名（兼容旧逻辑）
        import time
        stored_name = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:16]}{ext}"
        os.makedirs(upload_dir, exist_ok=True)
        safe_path = os.path.abspath(os.path.join(upload_dir, stored_name))
    
    upload_dir_abs = os.path.abspath(upload_dir)
    
    # 防止路径穿越：确保文件保存在upload_dir内
    if not safe_path.startswith(upload_dir_abs + os.sep) and safe_path != upload_dir_abs:
        raise HTTPException(status_code=400, detail="无效的文件路径")
    
    # 7. 保存文件
    try:
        with open(safe_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=_safe_detail(f"文件保存失败: {str(e)}"))
    
    # 8. 计算哈希
    file_hash = calculate_file_hash(content)
    
    return safe_path, safe_original_name, file_hash
