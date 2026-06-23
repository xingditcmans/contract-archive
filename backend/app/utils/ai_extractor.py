"""
AI 合同信息提取器 v1.0
统一的 AI 提供商接口，支持所有 OpenAI 兼容 API

支持提供商（开箱即用）：
- DeepSeek:     https://api.deepseek.com/v1
- 通义千问:      https://dashscope.aliyuncs.com/compatible-mode/v1
- 智谱 GLM:     https://open.bigmodel.cn/api/paas/v4
- Ollama 本地:   http://localhost:11434/v1
- OpenAI:       https://api.openai.com/v1
- 任何 OpenAI 兼容 API

使用方式：
    from app.utils.ai_extractor import AIExtractor
    extractor = AIExtractor()
    result = await extractor.extract(text, known_companies=["示例科技有限公司..."])
"""
from __future__ import annotations
import json
import logging
import os
import time
from typing import Optional, Dict, List, Any

logger = logging.getLogger("ai_extractor")

# 尝试导入 httpx（异步 HTTP 客户端）
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    httpx = None


# ========== 配置管理 ==========

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ai_config.json")

# 预设提供商模板（用户只需填 API Key 即可）
PROVIDER_PRESETS = {
    "deepseek": {
        "name": "DeepSeek",
        "api_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
        "pricing_note": "约 ¥1/百万token（极便宜）",
    },
    "qwen": {
        "name": "通义千问 (Qwen)",
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-max", "qwen-turbo"],
        "default_model": "qwen-plus",
        "pricing_note": "qwen-plus 约 ¥0.8/百万token",
    },
    "zhipu": {
        "name": "智谱 GLM",
        "api_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-flash", "glm-4-plus", "glm-4-air"],
        "default_model": "glm-4-flash",
        "pricing_note": "glm-4-flash 免费额度充足",
    },
    "ollama": {
        "name": "Ollama (本地)",
        "api_url": "http://localhost:11434/v1",
        "models": ["qwen3:7b", "qwen2.5:7b", "qwen2.5:3b", "deepseek-r1:7b"],
        "default_model": "qwen3:7b",
        "pricing_note": "免费（本地计算）",
    },
    "openai": {
        "name": "OpenAI",
        "api_url": "https://api.openai.com/v1",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        "default_model": "gpt-4o-mini",
        "pricing_note": "gpt-4o-mini 约 ¥1/百万token",
    },
    "custom": {
        "name": "自定义",
        "api_url": "",
        "models": [],
        "default_model": "",
        "pricing_note": "自行填写 API 地址和模型名",
    },
}


def _load_config() -> dict:
    """加载 AI 配置（文件不存在则返回默认值）"""
    defaults = {
        "enabled": False,
        "provider": "",
        "api_url": "",
        "api_key": "",
        "model": "",
        "max_tokens": 1024,
        "temperature": 0.1,
        "timeout_seconds": 60,
        "fallback_only": True,  # True=仅当正则识别不全时调用AI, False=每次都调用
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            defaults.update(saved)
    except Exception as e:
        logger.warning(f"读取 AI 配置文件失败: {e}")
    return defaults


def _save_config(config: dict) -> None:
    """保存 AI 配置"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_ai_config() -> dict:
    """获取当前 AI 配置（供 API 端点使用）"""
    config = _load_config()
    # 附加预设信息
    config["providers"] = PROVIDER_PRESETS
    config["available"] = HAS_HTTPX
    return config


def update_ai_config(new_config: dict) -> dict:
    """更新 AI 配置并返回完整配置"""
    current = _load_config()
    # 只更新提供的字段
    for key in ["enabled", "provider", "api_url", "api_key", "model",
                "max_tokens", "temperature", "timeout_seconds", "fallback_only"]:
        if key in new_config:
            current[key] = new_config[key]
    _save_config(current)
    logger.info(f"AI 配置已更新: provider={current.get('provider')}, enabled={current.get('enabled')}")
    return get_ai_config()


# ========== AI 提取器 ==========

CONTRACT_EXTRACTION_PROMPT = """你是一个专业的合同信息提取助手。请从以下 OCR 识别的合同文本中提取关键信息。

## 已知的我方公司列表
{known_companies_text}

## 提取规则
1. **合同名称**：合同标题或名称，通常在第一行或《》中
2. **我方公司**：从已知我方公司列表中选择，优先选择在甲方位置出现的
3. **对方公司**：乙方的完整公司名，不含"甲方""乙方"等标签
4. **合同金额**：合同总金额（数字），含"元""万元"单位
5. **签署日期**：合同签署日期，格式 YYYY-MM-DD

## 输出格式
严格按以下 JSON 格式输出，不要输出任何其他内容：

```json
{{
  "contract_name": "提取到的合同名称（没有则为null）",
  "our_company": "我方的完整公司名（没有则为null）",
  "counterparty": "对方的完整公司名（没有则为null）",
  "amount": "合同金额原文（没有则为null）",
  "sign_date": "YYYY-MM-DD（没有则为null）",
  "confidence": "整体置信度评估: high/medium/low"
}}
```

## OCR 文本
{ocr_text}"""


class AIExtractor:
    """统一的 AI 合同信息提取器"""

    def __init__(self):
        self.config = _load_config()

    def _build_client(self) -> httpx.AsyncClient:
        """构建 httpx 异步客户端"""
        if not HAS_HTTPX:
            raise RuntimeError("httpx 未安装，请执行: pip install httpx")

        cfg = _load_config()
        api_url = cfg.get("api_url", "").rstrip("/")
        api_key = cfg.get("api_key", "")

        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        return httpx.AsyncClient(
            base_url=api_url,
            headers=headers,
            timeout=httpx.Timeout(cfg.get("timeout_seconds", 60)),
        )

    def _needs_ai_fallback(self, ocr_result: dict) -> bool:
        """判断 OCR 正则结果是否需要 AI 兜底"""
        # 检查关键字段是否缺失
        critical_fields = ["contract_name", "our_company", "counterparty"]
        for field in critical_fields:
            if not ocr_result.get(field):
                return True
        # 如果合同名看起来像是 boilerplate，也需要 AI
        name = ocr_result.get("contract_name", "")
        boilerplate_starts = ["在签订", "签订本", "双方经", "本协议", "本合同", "合作期满"]
        if name and any(name.startswith(b) for b in boilerplate_starts):
            return True
        return False

    async def extract(
        self,
        ocr_text: str,
        known_companies: Optional[List[str]] = None,
        ocr_result: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        使用 AI 从 OCR 文本中提取合同信息

        Args:
            ocr_text: OCR 识别的原始文本
            known_companies: 已知的我方公司列表
            ocr_result: 已有的正则提取结果（用于判断是否需要 AI 兜底）

        Returns:
            提取结果 dict 或 None（失败时）
        """
        cfg = _load_config()

        # 检查是否启用
        if not cfg.get("enabled"):
            logger.debug("AI 提取已禁用")
            return None

        # 检查 fallback_only 模式
        if cfg.get("fallback_only", True) and ocr_result:
            if not self._needs_ai_fallback(ocr_result):
                logger.info("正则识别结果完整，跳过 AI 提取")
                return None

        if not HAS_HTTPX:
            logger.error("httpx 未安装，无法使用 AI 提取")
            return None

        api_url = cfg.get("api_url", "")
        api_key = cfg.get("api_key", "")
        model = cfg.get("model", "")

        if not api_url or not model:
            logger.warning("AI 配置不完整（缺少 api_url 或 model），跳过")
            return None

        # 构建提示词
        known_text = "\n".join(f"- {c}" for c in (known_companies or [])) if known_companies else "（无已知公司列表）"
        prompt = CONTRACT_EXTRACTION_PROMPT.format(
            known_companies_text=known_text,
            ocr_text=ocr_text[:8000],  # 限制文本长度，控制 token 消耗
        )

        logger.info(f"AI 提取请求: provider={cfg.get('provider')}, model={model}, text_length={len(ocr_text)}")

        start_time = time.time()
        try:
            async with self._build_client() as client:
                response = await client.post(
                    "/chat/completions",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": "你是一个专业的合同信息提取助手。只输出 JSON，不输出其他内容。"},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": cfg.get("max_tokens", 1024),
                        "temperature": cfg.get("temperature", 0.1),
                        "response_format": {"type": "json_object"},  # 强制 JSON 输出（部分模型不支持则忽略）
                    },
                )

                elapsed = time.time() - start_time

                if response.status_code != 200:
                    error_body = response.text[:500]
                    logger.error(f"AI API 返回错误 ({response.status_code}): {error_body}")
                    return None

                data = response.json()

                # 提取 token 用量
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)

                # 提取回复内容
                content = data["choices"][0]["message"]["content"]
                logger.info(
                    f"AI 提取完成: {elapsed:.1f}s, "
                    f"tokens={total_tokens} (prompt={prompt_tokens}, completion={completion_tokens})"
                )

                # 解析 JSON
                result = self._parse_response(content)
                if result is not None:
                    # 将 token 用量附加到结果中，供前端展示
                    result["_tokens"] = {
                        "prompt": prompt_tokens,
                        "completion": completion_tokens,
                        "total": total_tokens,
                        "elapsed_s": round(elapsed, 1),
                    }
                return result

        except httpx.TimeoutException:
            logger.error(f"AI API 请求超时 ({cfg.get('timeout_seconds', 60)}s)")
            return None
        except Exception as e:
            logger.error(f"AI 提取异常: {type(e).__name__}: {e}")
            return None

    def _parse_response(self, content: str) -> Optional[dict]:
        """解析 AI 返回的 JSON"""
        try:
            # 尝试直接解析
            result = json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 JSON 块（有些模型会包裹在 ```json ... ``` 中）
            import re
            m = re.search(r"\{[\s\S]*\}", content)
            if m:
                try:
                    result = json.loads(m.group(0))
                except json.JSONDecodeError:
                    logger.error(f"无法解析 AI 返回的 JSON: {content[:300]}")
                    return None
            else:
                logger.error(f"AI 返回内容不含 JSON: {content[:200]}")
                return None

        # 标准化字段
        extracted = {
            "contract_name": result.get("contract_name") or None,
            "our_company": result.get("our_company") or None,
            "counterparty": result.get("counterparty") or None,
            "amount": result.get("amount") or None,
            "sign_date": result.get("sign_date") or None,
            "ai_confidence": result.get("confidence", "unknown"),
            "_ai_extracted": True,
        }

        # 过滤掉 null 值
        return {k: v for k, v in extracted.items() if v is not None}


# 便捷函数：直接调用
async def ai_extract_contract_info(
    ocr_text: str,
    known_companies: Optional[List[str]] = None,
    ocr_result: Optional[dict] = None,
) -> Optional[dict]:
    """便捷函数：使用 AI 提取合同信息"""
    extractor = AIExtractor()
    return await extractor.extract(ocr_text, known_companies, ocr_result)
