"""
OCR 文字识别工具 v2.0
三层策略：pdfplumber（电子PDF） → PyMuPDF（不同引擎） → pytesseract（扫描件OCR）
图片OCR：pytesseract 中文+英文识别
"""
import re
import difflib
import logging
from io import BytesIO
from typing import Optional, List, Dict, Any
import os

import pdfplumber
from PIL import Image

logger = logging.getLogger("ocr")

# ========== 可选引擎检测 ==========

try:
    import pytesseract
    HAS_TESSERACT = True
    # 自动检测 tesseract 安装路径
    tesseract_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"/usr/bin/tesseract",
        r"/usr/local/bin/tesseract",
    ]
    for tp in tesseract_paths:
        if os.path.exists(tp):
            pytesseract.pytesseract.tesseract_cmd = tp
            break
except ImportError:
    HAS_TESSERACT = False

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


# ========== PDF 文字提取（三层回退） ==========

def extract_text_from_pdf(pdf_content: bytes) -> str:
    """
    从 PDF 中提取文字，自动选择最佳策略：
    ① pdfplumber — 电子版 PDF（最快）
    ② PyMuPDF — 不同解析引擎，覆盖 pdfplumber 的盲区
    ③ pytesseract OCR — 扫描件 PDF（需 tesseract）
    """
    # 策略①：pdfplumber
    text = _pdfplumber_extract(pdf_content)
    if _is_usable(text, threshold=50):
        logger.info(f"pdfplumber 提取成功：{len(text.strip())} 字符")
        return text

    # 策略②：PyMuPDF 文本提取
    logger.info(f"pdfplumber 仅得到 {len(text.strip())} 字符，尝试 PyMuPDF...")
    text = _pymupdf_extract_text(pdf_content)
    if _is_usable(text, threshold=50):
        logger.info(f"PyMuPDF 提取成功：{len(text.strip())} 字符")
        return text

    # 策略③：OCR 扫描件
    logger.info("尝试 OCR 识别（可能是扫描件）...")
    ocr_text = _pymupdf_ocr_pdf(pdf_content)
    if _is_usable(ocr_text, threshold=20):
        logger.info(f"OCR 识别成功：{len(ocr_text.strip())} 字符")
        return ocr_text

    # 全部失败，返回已有文本或空字符串
    if ocr_text:
        logger.warning(f"OCR 返回内容过少（{len(ocr_text.strip())} 字符），可能为空白页")
        return ocr_text
    if text:
        return text
    return ""


def diagnose_pdf_extraction(pdf_content: bytes) -> dict:
    """诊断 PDF 提取管道：逐层执行并返回每层的细节，用于排查 OCR 失败原因"""
    diag = {
        "engines": {
            "pdfplumber": True,       # pdfplumber 是必须依赖
            "pymupdf": HAS_PYMUPDF,
            "tesseract": HAS_TESSERACT,
            "tesseract_path": pytesseract.pytesseract.tesseract_cmd if HAS_TESSERACT else None,
        },
        "layers": [],
        "final_text": None,
    }

    # 层1：pdfplumber
    l1_text = ""
    l1_chars = 0
    try:
        with pdfplumber.open(BytesIO(pdf_content)) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    l1_text += t + "\n"
            l1_chars = len(l1_text.strip())
    except Exception as e:
        l1_text = f"[ERROR] {e}"

    has_chinese_l1 = bool(re.search(r'[\u4e00-\u9fff]', l1_text))
    diag["layers"].append({
        "name": "pdfplumber（电子PDF文本提取）",
        "usable": _is_usable(l1_text, threshold=50),
        "chars": l1_chars,
        "has_chinese": has_chinese_l1,
        "page_count": page_count if 'page_count' in dir() else 0,
        "sample": l1_text[:200] if l1_text else "",
    })

    # 层2：PyMuPDF 文本提取
    l2_text = ""
    l2_chars = 0
    if HAS_PYMUPDF:
        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            for page in doc:
                t = page.get_text()
                if t:
                    l2_text += t + "\n"
            l2_chars = len(l2_text.strip())
            doc.close()
        except Exception as e:
            l2_text = f"[ERROR] {e}"
    else:
        l2_text = "[SKIP] PyMuPDF (fitz) 未安装"

    has_chinese_l2 = bool(re.search(r'[\u4e00-\u9fff]', l2_text))
    diag["layers"].append({
        "name": "PyMuPDF（另一文本解析引擎）",
        "usable": _is_usable(l2_text, threshold=50) if HAS_PYMUPDF else False,
        "chars": l2_chars,
        "has_chinese": has_chinese_l2,
        "sample": l2_text[:200] if l2_text else "",
    })

    # 层3：OCR（PyMuPDF渲染 + Tesseract）
    l3_text = ""
    l3_chars = 0
    l3_pages_rendered = 0
    if HAS_PYMUPDF and HAS_TESSERACT:
        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            pages = list(doc)
            max_pages = min(len(pages), 10)
            for i in range(max_pages):
                page = pages[i]
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                t = pytesseract.image_to_string(img, lang="chi_sim+eng")
                if t and t.strip():
                    l3_text += f"[第{i+1}页]\n{t}\n\n"
                l3_pages_rendered += 1
            l3_chars = len(l3_text.strip())
            doc.close()
        except Exception as e:
            l3_text = f"[ERROR] {e}"
    elif not HAS_PYMUPDF:
        l3_text = "[SKIP] PyMuPDF 未安装，无法渲染 PDF 页面"
    elif not HAS_TESSERACT:
        l3_text = "[SKIP] Tesseract-OCR 未安装或 pytesseract 未导入"

    has_chinese_l3 = bool(re.search(r'[\u4e00-\u9fff]', l3_text))
    diag["layers"].append({
        "name": "OCR（PyMuPDF渲染+Tesseract识别）",
        "usable": _is_usable(l3_text, threshold=20),
        "chars": l3_chars,
        "has_chinese": has_chinese_l3,
        "pages_rendered": l3_pages_rendered,
        "sample": l3_text[:300] if l3_text else "",
    })

    # 找出可用层
    usable_layer = next(
        (ly for ly in diag["layers"] if ly["usable"]), None
    )
    diag["result"] = "success" if usable_layer else "all_failed"
    diag["winning_layer"] = usable_layer["name"] if usable_layer else None

    # 同时调用原函数获取最终文本
    diag["final_text"] = extract_text_from_pdf(pdf_content)

    return diag


def _is_usable(text: str, threshold: int = 30) -> bool:
    """判断文本是否足够可用（不含中文字符或过短视为无效）"""
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) < threshold:
        return False
    # 必须包含中文字符（否则可能是乱码或纯数字）
    if not re.search(r'[\u4e00-\u9fff]', stripped):
        return False
    return True


def _pdfplumber_extract(pdf_content: bytes) -> str:
    """pdfplumber 提取文字"""
    parts = []
    try:
        with pdfplumber.open(BytesIO(pdf_content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
    except Exception as e:
        logger.warning(f"pdfplumber 提取异常: {e}")
    return "\n".join(parts)


def _pymupdf_extract_text(pdf_content: bytes) -> str:
    """PyMuPDF 提取文字（内置文本层）"""
    if not HAS_PYMUPDF:
        return ""
    parts = []
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        for page in doc:
            text = page.get_text()
            if text:
                parts.append(text)
        doc.close()
    except Exception as e:
        logger.warning(f"PyMuPDF 提取异常: {e}")
    return "\n".join(parts)


def _pymupdf_ocr_pdf(pdf_content: bytes) -> str:
    """PyMuPDF 渲染页面为图片 → pytesseract OCR"""
    if not HAS_TESSERACT:
        logger.warning("pytesseract 未安装，无法进行 OCR")
        return ""

    parts = []
    try:
        if HAS_PYMUPDF:
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            pages = list(doc)
            max_pages = min(len(pages), 10)  # 最多 OCR 前10页
            for i in range(max_pages):
                page = pages[i]
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(img, lang="chi_sim+eng")
                if text and text.strip():
                    parts.append(f"[第{i+1}页]\n{text}")
            doc.close()
        else:
            # fallback: 用 pdfplumber 渲染页面为图片（不支持多页渲染，放弃）
            logger.warning("PyMuPDF 和 pdfplumber 均无法渲染 OCR，放弃")
            return ""
    except Exception as e:
        logger.error(f"PDF OCR 异常: {e}")
        return ""

    return "\n\n".join(parts)


# ========== 图片 OCR ==========

def extract_text_from_image(image_content: bytes) -> str:
    """从图片中 OCR 提取文字"""
    if HAS_TESSERACT:
        try:
            image = Image.open(BytesIO(image_content))
            # 预处理：转灰度提高识别率
            if image.mode != "L":
                image = image.convert("L")
            text = pytesseract.image_to_string(image, lang="chi_sim+eng")
            if text and len(text.strip()) > 10:
                logger.info(f"图片 OCR 成功：{len(text.strip())} 字符")
                return text
            logger.warning(f"图片 OCR 返回内容过少：{len(text.strip())} 字符")
        except Exception as e:
            logger.error(f"图片 OCR 异常: {e}")

    # 回退
    image = Image.open(BytesIO(image_content))
    width, height = image.size
    return (
        f"[图片信息] 尺寸: {width}×{height}\n\n"
        "⚠️ 无法进行 OCR 识别。\n"
        "请确保已安装 Tesseract-OCR:\n"
        "下载地址: https://github.com/UB-Mannheim/tesseract/wiki\n"
        "需勾选中文简体语言包 (chi_sim)"
    )


# ========== 合同关键字段提取 v3.0（正则 + 启发式兜底） ==========

# OCR 常见误识别纠正表
OCR_FIX_MAP = {
    "编亏": "编号", "编马": "编号", "编导": "编号", "编与": "编号",
    "合问": "合同", "合司": "合同", "合间": "合同", "合闫": "合同",
    "日朗": "日期", "日其月": "日期",
    "有限公同": "有限公司", "有限公局": "有限公司",
}


# 非公司名前缀（会从公司名提取结果中截断）
NON_COMPANY_PREFIXES = [
    "感谢您选择", "为您提供", "我司", "我方", "本公司", "我公司", "该公司",
    "由", "委托", "受托", "经", "通过", "依托", "借助", "凭借", "按照",
    # === 新增：合同定义/引用句式中的前缀 ===
    "甲方特聘", "乙方特聘", "甲方委托", "乙方委托",
    "是指", "指", "简称",
    # === 律师/顾问合同常见前缀 ===
    "特聘", "聘请", "聘用", "特约",
]


def _clean_company_name(name: str) -> str:
    """去掉公司名前的非公司前缀"""
    for prefix in NON_COMPANY_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):].lstrip()
    return name


def _preprocess_ocr(text: str) -> str:
    """预处理 OCR 文本：纠正常见误识别、归一化空白"""
    # 纠正常见误识别字符
    for wrong, correct in OCR_FIX_MAP.items():
        text = text.replace(wrong, correct)
    # OCR 经常把中文括号识别成书名号、英文括号等
    text = text.replace("\u300a", "\uff08").replace("\u300b", "\uff09")  # 《》 → （）
    text = text.replace("\u300e", "\uff08").replace("\u300f", "\uff09")  # 『』 → （）
    text = text.replace("\uff08", "（").replace("\uff09", "）")           # 全角英文括号统一为中文括号
    # OCR 常见标点误识别
    text = text.replace("\uff0c", "，").replace("\uff0e", "。")           # 全角英文逗号/句号 → 中文逗号/句号
    # === 新增：角色标签 OCR 纠错 ===
    text = text.replace("申方", "甲方")                                   # 申方 → 甲方
    text = text.replace("乙，方", "乙方").replace("甲，方", "甲方")       # 逗号干扰（中间）
    text = text.replace("，方：", "乙方：").replace("，方 :", "乙方：")   # 逗号在开头（,方：→乙方：）
    text = text.replace(",方：", "乙方：").replace(",方:", "乙方：")       # 半角逗号版本
    # 行首"方："大概率是"甲方："漏字（如"方：天津汇高花网酒店有限公司"）
    text = re.sub(r'^[ \t]*方\s*[：:：]\s*', '甲方：', text, flags=re.MULTILINE)
    # 归一化空白（保留单个空格，方便正则匹配）
    text = re.sub(r"[ \t]+", " ", text)
    # 保留 \\n 用于跨行匹配，但将 \\r\\n 统一为 \\n
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def extract_contract_info(raw_text: str, known_companies: Optional[List[Dict[str, Any]]] = None) -> dict:
    """从 OCR 文本中提取合同关键字段（正则优先 → 启发式兜底）

    Args:
        raw_text: OCR 原始文本
        known_companies: 已知我方公司列表 [{"id": 1, "name": "...", "keywords": "..."}, ...]
                        传入后会自动进行我方公司模糊匹配

    Returns:
        dict with contract_no, contract_name, counterparty, amount, date,
        matched_company_id, matched_company_name, counterparty_candidates
    """
    info = {
        "contract_no": None,
        "contract_name": None,
        "counterparty": None,
        "amount": None,
        "date": None,
        "matched_company_id": None,
        "matched_company_name": None,
        "counterparty_candidates": None,
    }

    if not raw_text or not raw_text.strip():
        return info

    # 预处理
    text = _preprocess_ocr(raw_text)
    text_single = text.replace("\n", " ")

    # ===== 逐字段提取：正则优先 → 启发式兜底 =====
    # 注意：合同编号不在此处识别（用户从外部平台复制粘贴，不在合同本身上）
    info["contract_name"] = _extract_contract_name(text_single, text) or _find_contract_name(text_single)
    info["amount"] = _extract_amount(text_single, text) or _find_amount(text_single)
    info["date"] = _extract_date(text_single, text) or _find_date(text_single)

    # ===== 公司双向匹配（我方 vs 对方）=====
    if known_companies:
        info = _match_our_company(info, text_single, text, known_companies)
    else:
        # 没有已知公司列表时，沿用旧逻辑
        info["counterparty"] = _extract_counterparty(text_single, text) or _find_company(text_single)

    # 清理 None 值
    result = {k: v for k, v in info.items() if v is not None}
    extracted_keys = [k for k in info if info[k] is not None]
    missed_keys = [k for k in info if info[k] is None]
    logger.info(f"提取到 {len(extracted_keys)}/{len(info)} 字段: {extracted_keys}；未命中: {missed_keys}")
    return result


# ============================================================
# 第一层：增强正则提取（标签匹配）
# ============================================================

def _extract_contract_name(text_single: str, text_multi: str) -> Optional[str]:
    """正则提取合同名称（自动过滤 boilerplate 文本）"""
    patterns = [
        # === 文档顶部第一行标题（最高优先级：许多合同名称就写在第一行，无任何标签） ===
        # 匹配：单独成行的、4-80字的合同/协议类标题
        r'(?:^|\n)\s*([\u4e00-\u9fa5a-zA-Z0-9（）()、，,·\s]{4,80}?(?:合同|协议|协议书|合同书))\s*(?:\n|$)',
        # === 标签式 ===
        r'(?:合同名称|协议名称|项目名称|合同标题|标题|事项|合同事由|合同\s*名称)\s*[：:：]\s*(.{4,150}?)(?:合同|协议|书|$)',
        # === 《XXX》书名号 ===
        r'《(.{4,120})》',
        # === 关键词引导：XX采购合同 / XX服务合同（含大量业务类型）===
        r'([\u4e00-\u9fa5a-zA-Z0-9（）()、，,，]{4,80})\s*(?:采购合同|销售合同|服务合同|委托合同|租赁合同|施工合同|合作协议|战略协议|框架协议|补充协议|合同书|协议书|买卖合同|技术合同|开发合同|维保合同|咨询合同|咨询服务|技术服务|认证书|认证合同|认证协议|接入服务|接入协议|供应协议|供货合同|供水协议|饮用水|用水协议|饮用水供应|销售协议|代理协议|运输合同|物流合同|仓储合同|保险合同|担保合同|抵押合同|借款合同|投融资|投资协议|保密协议|竞业限制|外包合同|劳务派遣|培训合同|使用许可|使用合同|版权合同|授权合同)',
        # === OCR 书名号变体 ===
        r'<\s*([\u4e00-\u9fa5a-zA-Z0-9（）()]{4,120})\s*(?:合同|协议)\s*>',
        # === 反序：合同/协议关键词引导 ===
        r'(?:采购|销售|服务|委托|租赁|施工|合作|战略|框架|补充|买卖|技术|开发|维保|咨询|设计|监理|认证|接入|供应|供水|运输|物流|保险|担保|借款|融资|投资|保密|外包|派遣|培训)\s*[合同协议书]+\s*[：:：]?\s*([\u4e00-\u9fa5a-zA-Z0-9（）()]{2,80})',
    ]
    for pat in patterns:
        m = re.search(pat, text_multi, re.MULTILINE) if '\\n' in pat or pat.startswith(r'(?:^') else re.search(pat, text_single)
        if m:
            name = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)
            name = _clean(name)
            if 4 <= len(name) <= 150 and not _is_boilerplate(name):
                return name
    return None


def _extract_counterparty(text_single: str, text_multi: str) -> Optional[str]:
    """正则提取对方公司（要求匹配结果含公司名后缀，防止捕获合同条款文字）"""
    # 付款信息标签（新增）—— 合同末尾付款详情区域，格式整齐，OCR 准确率高
    PAYMENT_LABELS = r'收款方|开户名|户名|账户名称|收款单位|收款人|乙方账户|对公账户|付款方'
    COMPANY_SUFFIXES = ["有限公司", "股份有限公司", "集团公司", "中心", "工厂", "厂",
                        "事务所", "工作室", "学校", "学院", "医院", "银行", "合作社",
                        "研究院", "研究所"]
    OUR_KEYWORDS = []  # 从数据库动态读取，详见 companies 表 keywords 字段
    # OCR 把角色标签和机构类型粘连产生的假公司名（如"乙方银行"、"甲方学校"）
    ROLE_PREFIXES = ["甲方", "乙方", "甲、乙方", "甲乙方", "双方", "各方", "一方", "另一方"]

    def _is_valid_counterparty(cp):
        cp = _clean_company_name(cp)
        if not cp or not (4 <= len(cp) <= 80):
            return None
        if cp.startswith("合同"):
            return None
        if any(kw in cp for kw in OUR_KEYWORDS):
            return None
        if _is_definition_context(cp, text_multi):
            return None
        if any(cp.startswith(rp) for rp in ROLE_PREFIXES):
            return None
        # 有合法后缀（含分公司/办事处）即可
        if any(s in cp for s in COMPANY_SUFFIXES):
            return cp
        # 分公司/办事处后缀
        if re.search(r'(?:分公司|办事处|分支机构|子公司)$', cp):
            return cp
        return None

    # === 优先级1：乙方角色标签 + 公司名（含分公司）===
    role_pattern = r'(?:乙\s*方|卖\s*方|供\s*方|需\s*方|对方|供应商|客户|受托方|委托方|承包方|中标方|中标单位|供货单位|服务商|乙方单位|认证方|服务方|提供方|咨询方|设计方|施工方|监理方|审计方|评估方|检测方|代理方|承运方)\s*[：:：]\s*([\u4e00-\u9fa5a-zA-Z0-9（）()（）、,，\s]{4,60})'
    for m in re.finditer(role_pattern, text_multi):
        cp_raw = m.group(1)
        cp = _clean(cp_raw)
        valid = _is_valid_counterparty(cp)
        if valid:
            return valid
    # 乙方跨行
    m = re.search(r'乙\s*方\s*[：:：]*\s*\n\s*([\u4e00-\u9fa5a-zA-Z（）()·]{4,60})', text_multi)
    if m:
        cp = _clean(m.group(1))
        valid = _is_valid_counterparty(cp)
        if valid:
            return valid

    # === 优先级2：付款信息标签 + 公司名 ===
    payment_pattern = rf'(?:{PAYMENT_LABELS})\s*[：:：]?\s*([\u4e00-\u9fa5a-zA-Z（）()·]{{4,60}}(?:有限公司|股份有限公司|集团公司|中心|工厂|厂|事务所|工作室)(?:[\u4e00-\u9fa5a-zA-Z（）(){{}}]{{1,20}}(?:分公司|办事处))?)'
    m = re.search(payment_pattern, text_multi)
    if m:
        cp = _clean(m.group(1))
        valid = _is_valid_counterparty(cp)
        if valid:
            return valid

    # === 优先级3：全文扫描公司名模式 ===
    all_matches = re.findall(
        r'([\u4e00-\u9fa5a-zA-Z（）()·]{2,60}(?:有限公司|股份有限公司|集团公司|中心|工厂|厂|事务所|工作室|学校|学院|医院|银行|合作社)(?:[\u4e00-\u9fa5a-zA-Z（）()]{1,20}(?:分公司|办事处|分支机构))?)',
        text_single
    )
    for cp_raw in all_matches:
        cp = _clean(cp_raw)
        valid = _is_valid_counterparty(cp)
        if valid:
            return valid

    return None


def _extract_amount(text_single: str, text_multi: str) -> Optional[str]:
    """正则提取金额"""
    amounts = []
    patterns = [
        # === 标签 + 金额 ===
        r'(?:合同金额|合同总价|总价款|合同价款|总金额|价款|成交金额|合同总金额|预算金额|预算|预估金额|金额合计|合计金额)\s*[：:：]\s*[¥￥Yy]?\s*([\d,，.\s]+)\s*(?:元|万元|万)',
        # === ¥ ￥ 引导 ===
        r'[¥￥]\s*([\d,，.\s]+)\s*(?:元|万元|万)?',
        # === OCR 误识别：Y / y 可能是 ¥ ===
        r'[Yy]\s*([\d,，.\s]+)\s*(?:元|万元|万)',
        # === 数字 + 元（不在标签后的自由金额） ===
        r'([\d,，.\s]{1,15})\s*(?:万元|万|元整|元)',
    ]
    for pat in patterns:
        for m in re.findall(pat, text_single, re.IGNORECASE):
            clean_val = str(m).replace(",", "").replace("，", "").replace(" ", "").strip()
            try:
                val = float(clean_val)
                if 0 < val < 999999999:
                    amounts.append((clean_val, val))
            except ValueError:
                pass

    if amounts:
        # 排除明显是日期或编号的值
        amounts = [(s, v) for s, v in amounts if not (10000000 <= v <= 20991231)]  # 排除日期格式
        if amounts:
            amounts.sort(key=lambda x: x[1], reverse=True)
            return amounts[0][0]
    return None


def _extract_date(text_single: str, text_multi: str) -> Optional[str]:
    """正则提取日期"""
    patterns = [
        # === 标签 + 日期 ===
        r'(?:签订日期|签署日期|签约日期|合同日期|生效日期|签订时间|申请日期|提交日期|日期|时间|制单日期|填表日期)\s*[：:：]\s*(\d{4}\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}\s*日?)',
        # === 中文日期 ===
        r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
        # === ISO 格式 ===
        r'(\d{4}[-/]\d{2}[-/]\d{2})',
        # === 紧凑中文 ===
        r'(\d{4})年(\d{1,2})月(\d{1,2})日',
    ]
    for pat in patterns:
        m = re.search(pat, text_single)
        if m:
            if m.lastindex and m.lastindex >= 3:
                # 分组模式：年/月/日 分别捕获
                date_str = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            else:
                date_str = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)
                date_str = _clean(date_str)
                date_str = date_str.replace("年", "-").replace("月", "-").replace("日", "")
                date_str = date_str.replace("/", "-").replace(".", "-").replace(" ", "")
            if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
                # 验证日期合理性
                try:
                    y, mth, d = date_str.split("-")
                    if 2020 <= int(y) <= 2030 and 1 <= int(mth) <= 12 and 1 <= int(d) <= 31:
                        return date_str
                except ValueError:
                    pass
    return None


# ============================================================
# 第二层：无标签启发式提取（全文模式扫描）
# ============================================================

# ============================================================
# 第三层：公司名双向匹配（我方 vs 对方）
# ============================================================

def _extract_all_companies(text: str) -> List[str]:
    """扫描文本中所有公司名模式（不排除任何公司），返回去重后的列表"""
    # 注意：分公司/办事处/分支机构 用独立的更宽泛正则匹配，因为它们附在"有限公司"后面
    pattern = r"([\u4e00-\u9fa5a-zA-Z（）()·《》〔〕【】「」『』\u3010\u3011]{2,60}(?:有限公司|股份有限公司|集团公司|中心|工厂|厂|事务所|工作室|学校|学院|医院|银行|合作社|研究院|研究所|基金会|协会|委员会|机关|政府|局|站|队|部|所)(?:[\u4e00-\u9fa5a-zA-Z（）()]{1,20}(?:分公司|办事处|分支机构|子公司))?)"
    matches = re.findall(pattern, text)
    # 去重，保留最长版本
    seen = set()
    result = []
    for m in sorted(matches, key=len, reverse=True):
        # 如果这个公司名是另一个公司名的子串，跳过短的
        if not any(m in other and m != other for other in seen):
            if m not in seen:
                seen.add(m)
                result.append(m)
    return result


def _extract_all_companies_multi(text_single: str, text_multi: str) -> List[str]:
    """二维扫描：同时从单行文本（含空格）和无换行文本（换行拼接）中提取公司名

    OCR 经常把跨行公司名拆开（如「国信\n桥数字科技」→ text_single 变成「国信 桥数字科技」，
    空格不在公司名正则字符集中导致匹配失败）。本函数同时尝试 text_multi.replace("\\n", "")，
    把换行处直接拼接（变成「国信桥数字科技」），确保跨行公司名能被正则捕获。
    """
    all_matches = []

    # 公司/机构后缀模式（与 _extract_all_companies 保持同步，含分公司/办事处后缀）
    _COMPANY_PATTERN = r"([\u4e00-\u9fa5a-zA-Z（）()·《》〔〕【】「」『』\u3010\u3011]{2,60}(?:有限公司|股份有限公司|集团公司|中心|工厂|厂|事务所|工作室|学校|学院|医院|银行|合作社|研究院|研究所|基金会|协会|委员会|机关|政府|局|站|队|部|所)(?:[\u4e00-\u9fa5a-zA-Z（）()]{1,20}(?:分公司|办事处|分支机构|子公司))?)"

    # 维度1：单行文本（含空格）
    matches1 = re.findall(_COMPANY_PATTERN, text_single)
    all_matches.extend(matches1)

    # 维度2：无换行文本（直接拼接，解决跨行截断）
    text_no_nl = text_multi.replace("\n", "").replace("\r", "")
    if text_no_nl != text_single:
        matches2 = re.findall(_COMPANY_PATTERN, text_no_nl)
        all_matches.extend(matches2)

    # === 清洗前缀：截断非公司名前缀 ===
    ROLE_PREFIXES_STRIP = ["甲方", "乙方", "甲、乙方", "甲乙方", "双方", "各方", "一方", "另一方"]
    cleaned_matches = []
    for m in all_matches:
        cleaned = _clean_company_name(m)
        if not cleaned or len(cleaned) < 4:
            continue
        # 过滤角色标签粘连假公司名（如"乙方银行"、"甲方学校"）
        if any(cleaned.startswith(rp) for rp in ROLE_PREFIXES_STRIP):
            continue
        cleaned_matches.append(cleaned)

    # 去重，保留最长版本
    seen = set()
    result = []
    for m in sorted(cleaned_matches, key=len, reverse=True):
        if not any(m in other and m != other for other in seen):
            if m not in seen:
                seen.add(m)
                result.append(m)
    return result


def _fuzzy_match(text_fragment: str, candidates: List[Dict[str, Any]], threshold: float = 0.55) -> Optional[Dict[str, Any]]:
    """模糊匹配：OCR 识别到的公司名片段 → 已知公司列表

    Args:
        text_fragment: OCR 提取到的公司名文本片段
        candidates: 已知公司列表 [{"id": 1, "name": "...", "keywords": "..."}]
        threshold: 相似度阈值（0-1），超过此值才认为匹配成功

    Returns:
        匹配到的公司 dict，或 None
    """
    best_score = 0.0
    best_match = None

    # 通用后缀（4 字连续匹配时需要排除这些）
    GENERIC_SUFFIXES = ["有限公司", "有限责任", "股份有限", "集团公司", "科技有限",
                        "责任公司", "合伙企业", "事务所", "工作室", "中心", "厂"]

    for company in candidates:
        score = 0.0

        # 1) 比对完整公司名
        score = difflib.SequenceMatcher(None, text_fragment, company["name"]).ratio()

        # 2) 比对关键词列表
        if company.get("keywords"):
            for kw in company["keywords"].split(","):
                kw = kw.strip()
                if kw:
                    kw_score = difflib.SequenceMatcher(None, text_fragment, kw).ratio()
                    score = max(score, kw_score)

        # 3) 特判：公司名核心部分包含关系
        #   OCR 可能只识别出「国信蓝桥」而非全名「国信蓝桥数字科技（北京）有限公司」
        short = min(len(text_fragment), len(company["name"]))
        if short >= 4:
            # 检查 OCR 文本是否是公司名的子串，或公司名是否是 OCR 文本的子串
            if text_fragment[:min(8, len(text_fragment))] in company["name"]:
                score = max(score, 0.75)
            if company["name"][:min(8, len(company["name"]))] in text_fragment:
                score = max(score, 0.75)

        # 4) 【v3.3 新增】4 字连续窗口匹配：OCR 文本和公司名中任意 4 个连续
        #    中文字符相同（排除"有限公司"等通用后缀），直接高分匹配
        #    解决 OCR 括号/标点误识别导致 SequenceMatcher 分数被拉低的问题
        #    例如：「国信蓝桥数字科技《北京》有限公司」vs「国信蓝桥数字科技（北京）有限公司」
        if score < 0.80:
            chunk_score = _four_char_chunk_match(text_fragment, company["name"], GENERIC_SUFFIXES)
            if chunk_score > 0:
                score = max(score, chunk_score)

        if score > best_score:
            best_score = score
            best_match = company

    # 最低质量检查：防止仅靠"北京""有限公司"等通用词组匹配
    if best_score < threshold:
        return None
    if best_match:
        match = difflib.SequenceMatcher(None, text_fragment, best_match["name"])
        longest = match.find_longest_match(0, len(text_fragment), 0, len(best_match["name"]))
        common_suffixes = ["有限公司", "有限责任公司", "股份有限公司", "科技有限公司",
                          "集团公司", "中心", "事务所", "工作室"]
        GENERIC_ONLY = ["有限公司", "有限责任", "股份有限", "集团公司", "科技有限",
                        "责任公司", "合伙企业", "事务所", "工作室", "中心", "厂",
                        "北京", "上海", "深圳", "广州", "杭州", "南京", "天津"]
        matched_text = text_fragment[longest.a:longest.a + longest.size]

        # 检查1：最长公共子串是否为纯通用词（且匹配分数不够高）
        if longest.size <= 3 and best_score < 0.80:
            if matched_text in GENERIC_ONLY or matched_text in common_suffixes:
                logger.debug(f"模糊匹配拒绝: 「{text_fragment}」最长子串「{matched_text}」为通用词")
                return None

        # 检查2：公共子串被通用后缀包含
        is_generic = any(suffix in matched_text and len(matched_text) <= len(suffix) + 2
                        for suffix in common_suffixes)
        if is_generic and best_score < 0.80:
            logger.debug(f"模糊匹配拒绝: 「{text_fragment}」最长子串「{matched_text}」为通用词")
            return None

    logger.debug(f"模糊匹配: 「{text_fragment}」 → best={best_match['name'] if best_match else 'None'}, score={best_score:.2f}")
    return best_match


def _four_char_chunk_match(ocr_text: str, company_name: str, generic_suffixes: List[str]) -> float:
    """4 字连续窗口匹配：按匹配到的 4 字块数量分级给分

    解决共享前缀歧义（如多个子公司都以"国信蓝桥"开头）：
    "国信蓝桥数字科技（北京）" vs "国信蓝桥数字科技（北京）有限公司" → 8+ 块匹配 → 高分
    "国信蓝桥数字科技（北京）" vs "国信蓝桥教育科技股份有限公司" → 仅前4块匹配 → 低分

    排除"有限公司""有限责任"等通用后缀，防止无关公司靠这些词误匹配。

    Returns:
        匹配得分：按匹配块数量计算（0.60 ~ 0.90），或 0.0（无匹配）
    """
    # 提取纯中文（去掉标点符号，方便窗口对齐）
    ocr_chinese = re.sub(r'[^\u4e00-\u9fff]', '', ocr_text)
    name_chinese = re.sub(r'[^\u4e00-\u9fff]', '', company_name)

    if len(ocr_chinese) < 4 or len(name_chinese) < 4:
        return 0.0

    # 从 OCR 文本中取所有 4 字窗口
    ocr_chunks = set()
    for i in range(len(ocr_chinese) - 3):
        chunk = ocr_chinese[i:i+4]
        if chunk not in generic_suffixes:
            ocr_chunks.add(chunk)

    # 从公司名中取所有 4 字窗口，统计匹配数
    matched_count = 0
    matched_samples = []
    for i in range(len(name_chinese) - 3):
        chunk = name_chinese[i:i+4]
        if chunk in generic_suffixes:
            continue
        if chunk in ocr_chunks:
            matched_count += 1
            if matched_count <= 5:
                matched_samples.append(chunk)

    if matched_count == 0:
        return 0.0

    # 按匹配块数量分级给分（块越多置信度越高）
    if matched_count >= 8:
        score = 0.90
    elif matched_count >= 5:
        score = 0.85
    elif matched_count >= 3:
        score = 0.75
    elif matched_count >= 1:
        score = 0.60  # 仅1-2块匹配，可能是巧合，给低分

    logger.debug(f"  4字窗口: {matched_count}块匹配 ({', '.join(matched_samples[:3])}...) → 得分 {score:.2f}")
    return score


def _extract_company_from_payment_info(text: str) -> Optional[str]:
    """从付款信息区域直接提取对方公司名（高置信度独立通道）

    付款详情通常位于合同末尾（~80%位置），格式极其整齐：
        收款方：北京某某科技有限公司
        开户行：中国工商银行某某支行
        账号：1234567890

    这部分 OCR 识别准确率远高于合同正文（因排版规整、无复杂背景），
    且「收款方/开户名/户名」后面的公司名几乎一定是对方的完整法定名称。

    本函数独立于 _extract_counterparty，作为第二个验证通道。
    """
    payment_patterns = [
        # 标签 + 公司名（严格要求有限公司等后缀，确保是公司而非个人名）
        r'(?:收款方|开户名|户名|账户名称|收款单位|收款人|乙方账户|对公账户)[：:：\s]*([\u4e00-\u9fa5a-zA-Z（）()·]{4,50}(?:有限公司|股份有限公司|集团公司|中心|工厂|厂|事务所|工作室))',
        # 跨行模式（标签在上行，公司名在下行）
        r'(?:收款方|开户名|户名|账户名称|收款单位)\s*[：:：]?\s*\n\s*([\u4e00-\u9fa5a-zA-Z（）()·]{4,50}(?:有限公司|股份有限公司|集团公司))',
    ]

    for pat in payment_patterns:
        m = re.search(pat, text)
        if m:
            company = m.group(1).strip()
            company = _clean(company)
            company = _clean_company_name(company)
            if 4 <= len(company) <= 80:
                logger.info(f"  付款信息提取对方公司: 「{company}」")
                return company

    return None


def _is_definition_context(company_name: str, text: str) -> bool:
    """判断公司名是否出现在合同定义/解释条款的上下文中（如"是指XXX有限公司"）

    这类公司名通常是合同术语定义，不是真正的对方公司。
    例如：「"产权交易机构"是指承担产权交易的场所及其主体北京产权交易所有限公司」
    """
    pos = text.find(company_name)
    if pos < 0:
        return False
    # 检查公司名前50字符内是否有定义性词语
    context_before = text[max(0, pos - 50): pos]
    definition_markers = ["是指", "指的是", "简称", "以下简称", "以下称为", "以下称",
                          "\"", '"', "『", "」", "定义为", "术语"]
    for marker in definition_markers:
        if marker in context_before:
            logger.debug(f"  定义上下文过滤: 「{company_name}」(前文含「{marker}」)")
            return True
    return False


def _pick_counterparty(text: str, candidates: List[str]) -> Optional[str]:
    """从候选公司中智能选择对方公司：优先「乙方/供方/卖方」标签附近的公司名
    
    返回匹配到的公司名，或 None（表示无明确线索）
    """
    # 对方标签列表（乙方/供方/卖方/认证方/受托方等角色 + 付款信息标签）
    counterparty_labels = [
        "乙方", "卖方", "供方", "需方", "对方", "供应商", "客户",
        "受托方", "委托方", "承包方", "中标方", "中标单位", "供货单位", "服务商",
        "乙方单位", "受托单位", "供应单位",
        "认证方", "服务方", "提供方", "咨询方", "设计方", "施工方",
        "监理方", "审计方", "评估方", "检测方", "代理方", "承运方",
        "出租方", "承租方", "出借方", "借用方", "许可方", "被许可方",
        # === 付款信息标签（合同末尾~80%位置，格式整齐，OCR准确率高） ===
        "收款方", "开户名", "户名", "账户名称", "收款单位", "收款人",
        "乙方账户", "对公账户", "付款方",
    ]

    # 有效公司名后缀（只有含这些后缀的候选才能被选中）
    VALID_SUFFIXES = ["有限公司", "股份有限", "集团公司", "中心", "事务所", "工作室",
                      "学校", "学院", "医院", "研究院", "研究所", "基金会",
                      "分公司", "办事处", "分支机构", "子公司"]

    best_score = 0
    best_candidate = None
    
    for candidate in candidates:
        # === 必须有合法公司名后缀，否则跳过（防止"域名和网站"等垃圾进入） ===
        if not any(s in candidate for s in VALID_SUFFIXES):
            continue

        # === 新增：跳过出现在定义/解释条款上下文中的公司名 ===
        if _is_definition_context(candidate, text):
            logger.info(f"  跳过定义上下文公司: 「{candidate}」")
            continue

        for label in counterparty_labels:
            # 在文本中查找"标签"和"公司名"的接近程度
            label_pos = text.find(label)
            candidate_pos = text.find(candidate)
            if label_pos >= 0 and candidate_pos >= 0:
                # 计算距离，越近越好
                distance = abs(candidate_pos - label_pos)
                # 如果在 80 字符以内，认为相关（扩大到80覆盖分公司全称场景）
                if distance < 80:
                    score = 1.0 - (distance / 80.0)  # 距离越近分越高
                    if score > best_score:
                        best_score = score
                        best_candidate = candidate
    
    if best_candidate:
        logger.info(f"  对方公司选定: 「{best_candidate}」(标签距离得分 {best_score:.2f})")
    
    return best_candidate


def _match_our_company(info: dict, text_single: str, text_multi: str, known_companies: List[Dict[str, Any]]) -> dict:
    """公司双向匹配：先找 OCR 中所有公司名 → 模糊匹配已知列表 → 分类我方/对方

    Args:
        info: 当前提取结果 dict
        text_single: OCR 单行文本（用于 regex 匹配）
        text_multi: OCR 多行文本（用于距离计算，保留换行位置信息）
        known_companies: 我方公司列表

    Returns:
        更新后的 info dict
    """
    # 步骤1：从文本中提取所有公司名（二维搜索：单行 + 无换行拼接）
    all_companies = _extract_all_companies_multi(text_single, text_multi)
    if not all_companies:
        # 没有公司名，回退到旧逻辑
        info["counterparty"] = _extract_counterparty(text_single, text_multi) or None
        return info

    logger.info(f"OCR 提取到 {len(all_companies)} 个公司名: {all_companies}")

    # 步骤2：逐一模糊匹配已知公司
    our_matches = []       # 匹配到我方公司的
    unmatched = []         # 未匹配到（候选对方公司）

    for company_name in all_companies:
        matched = _fuzzy_match(company_name, known_companies)
        if matched:
            our_matches.append({"ocr_name": company_name, "company": matched})
            logger.info(f"  我方公司匹配: 「{company_name}」 → {matched['name']} (id={matched['id']})")
        else:
            unmatched.append(company_name)

    # 步骤3：填充结果
    if our_matches:
        # 取最佳匹配（第一个匹配到的）
        best = our_matches[0]
        info["matched_company_id"] = best["company"]["id"]
        info["matched_company_name"] = best["company"]["name"]

    if unmatched:
        info["counterparty_candidates"] = unmatched
        # 智能选择对方公司：用原始多行文本做距离计算（标签和公司名在相邻行也有效）
        counterparty = _pick_counterparty(text_multi if text_multi else text_single, unmatched)
        if counterparty:
            info["counterparty"] = counterparty
        else:
            # 未找到时：优先选有完整公司名后缀的（或分公司），否则取第一个
            preferred = next(
                (c for c in unmatched if any(s in c for s in ["有限公司", "股份有限", "分公司", "办事处", "学院", "研究院"])),
                unmatched[0]
            )
            info["counterparty"] = preferred

    # 如果没有通过模糊匹配找到 counterparty，尝试旧逻辑
    if not info.get("counterparty"):
        info["counterparty"] = _extract_counterparty(text_single, text_multi) or None

    # === 付款信息高置信度兜底（即使已有counterparty也验证，替换错误匹配） ===
    payment_company = _extract_company_from_payment_info(text_multi)
    if payment_company:
        # 验证：付款信息中的公司不能是我方公司
        is_our = _fuzzy_match(payment_company, known_companies) if known_companies else False
        if not is_our:
            current_cp = info.get("counterparty")
            # 如果当前没有对方公司，直接用付款信息
            if not current_cp:
                info["counterparty"] = payment_company
                logger.info(f"  对方公司来自付款信息（兜底）: 「{payment_company}」")
            # 如果当前对方公司不含有限公司后缀但付款信息有 → 替换
            elif not any(s in (current_cp or "") for s in ["有限公司", "股份有限"]):
                if any(s in payment_company for s in ["有限公司", "股份有限"]):
                    logger.info(f"  对方公司替换（付款信息更准确）: 「{current_cp}」 → 「{payment_company}」")
                    info["counterparty"] = payment_company

    return info


def _find_date(text: str) -> Optional[str]:
    """启发式：扫描文本中所有日期格式"""
    # 中文日期：YYYY年MM月DD日
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        y, mt, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 2020 <= y <= 2030 and 1 <= mt <= 12 and 1 <= d <= 31:
            return f"{y}-{mt:02d}-{d:02d}"
    # ISO 格式：YYYY-MM-DD
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        try:
            y, mt, d = map(int, m.group(1).split("-"))
            if 2020 <= y <= 2030 and 1 <= mt <= 12 and 1 <= d <= 31:
                return m.group(1)
        except ValueError:
            pass
    # 紧凑格式：YYYY/MM/DD 或 YYYY.MM.DD
    m = re.search(r"(\d{4})[/.](\d{1,2})[/.](\d{1,2})", text)
    if m:
        y, mt, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 2020 <= y <= 2030 and 1 <= mt <= 12 and 1 <= d <= 31:
            return f"{y}-{mt:02d}-{d:02d}"
    return None


def _find_amount(text: str) -> Optional[str]:
    """启发式：扫描文本中所有金额模式"""
    patterns = [
        r"[¥￥Yy]?\s*([\d,，.\s]{1,15})\s*(?:万元|万|元整|元)(?!\s*[每只个])",
    ]
    amounts = []
    for pat in patterns:
        for m in re.findall(pat, text, re.IGNORECASE):
            clean_val = str(m).replace(",", "").replace("，", "").replace(" ", "").strip()
            try:
                val = float(clean_val)
                if 0 < val < 999999999:
                    amounts.append((clean_val, val))
            except ValueError:
                pass

    if amounts:
        # 排除日期格式的值
        amounts = [(s, v) for s, v in amounts if not (10000000 <= v <= 20991231)]
        if amounts:
            amounts.sort(key=lambda x: x[1], reverse=True)
            return amounts[0][0]
    return None


def _find_contract_name(text: str) -> Optional[str]:
    """启发式：扫描文本中的合同名称（过滤 boilerplate）"""
    # 书名号包裹
    m = re.search(r"[《「](.{4,120})[》」]", text)
    if m:
        name = _clean(m.group(1))
        if not _is_boilerplate(name):
            return name
    # 以完整后缀结尾的合同名（后缀从长到短排列，防止"协议"先于"协议书"匹配）
    m = re.search(r"([\u4e00-\u9fa5a-zA-Z0-9（）()、，,，\s]{4,120}?(?:协议书|合同书|合同|协议|使用许可|服务合同|授权协议))", text)
    if m:
        name = _clean(m.group(0))  # 完整匹配（含后缀）
        if not _is_boilerplate(name):
            return name
    # 纯名称模式：以服务/业务/项目等关键词开头的一行标题
    m = re.search(r"(?:^|\n)\s*([\u4e00-\u9fa5a-zA-Z0-9（）()、，,，]{4,80}?(?:服务|业务|采购|销售|施工|租赁|设计|开发|咨询|认证|供应|接入|维护|管理|外包|派遣|使用许可|授权|许可)(?:[合同协议]+书?))\s*(?:\n|$)", text)
    if m:
        name = _clean(m.group(1))
        if not _is_boilerplate(name):
            return name
    return None


# ===== boilerplate 黑名单（合同条款套话，不能作为合同名称） =====
BOILERPLATE_PATTERNS = [
    r'^在签订', r'^签订本', r'^签署本', r'^本协议', r'^本合同',
    r'^双方经', r'^经双方', r'^经友好', r'^签约', r'^签字',
    r'^盖章', r'^甲方', r'^乙方', r'^鉴于', r'^根据',
    r'^依照', r'^为保护', r'^为明确', r'^为规范', r'^为保障',
    r'^按照', r'^依据', r'^遵照', r'^遵循', r'^第一条',
    r'^第[一二三四五六七八九十]', r'^总\s*则', r'^定义',
    r'合同$', r'协议$', r'书$',  # 纯"合同"/"协议"/"书"无意义
    # === 新增：合同条款正文常见开头 ===
    r'^合作期满', r'^合同期满', r'^协议期满',
    r'^是指承担', r'^是指', r'^指的是',
    r'^承担', r'^负责', r'^负有',
    r'^不得', r'^禁止', r'^任何一方',
    r'^如发生', r'^如出现', r'^如遇',
    r'^损害赔偿', r'^违约责任', r'^争议解决',
    r'^本合同自', r'^本协议自', r'^合同自',
]


def _is_boilerplate(text: str) -> bool:
    """判断文本是否为合同条款套话（不能作为合同名称）"""
    text = text.strip()
    if len(text) <= 3:
        return True  # 太短无意义
    for pat in BOILERPLATE_PATTERNS:
        if re.search(pat, text):
            logger.debug(f"  boilerplate 过滤: 「{text}」(匹配 {pat})")
            return True
    return False


def _clean(text: str) -> str:
    """清理文本：去首尾空白和多余标点"""
    return text.strip().strip("：：:。，,；;. （）() ").strip()
