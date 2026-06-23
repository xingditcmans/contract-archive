<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue-3-4FC08D?logo=vue.js" alt="Vue 3">
  <img src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite" alt="SQLite">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
</p>

<h1 align="center">📁 合同归档管理系统</h1>

<p align="center">
  面向中小型企业的轻量级合同归档解决方案<br>
  OCR 智能识别 · 全文检索 · 多环境一键部署
</p>

---

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 📄 **合同录入** | 支持 PDF / 图片 / Word 附件上传，OCR + AI 双引擎智能提取关键字段 |
| 🔍 **多维查询** | 多条件组合筛选、关键词模糊搜索、分页浏览、Excel 导出 |
| 📦 **批量导入** | 上传 Excel 台账 + PDF 附件文件夹，一键批量导入历史合同 |
| 🔐 **权限管理** | 管理员 / 普通用户两级角色，账户锁定防暴力破解 |
| ⚡ **AI 增强识别** | 可选接入 OpenAI / Ollama 等大模型，自动补充 OCR 遗漏字段 |
| 💾 **备份恢复** | 按年份 / 类型筛选备份，支持 ZIP 打包下载和导入恢复 |
| 🗂 **附件管理** | 多附件上传、在线预览、下载、关联管理 |
| 🐳 **一键部署** | 支持 Linux 直接部署 / Docker / Windows 三种方式 |

## 🏗 技术架构

```
┌─────────────────────────────────────┐
│         Vue 3 (Vite) 前端            │
│     Element Plus 组件库              │
├─────────────────────────────────────┤
│      FastAPI 后端 (REST API)         │
│    SQLAlchemy ORM · JWT 认证         │
├─────────────────────────────────────┤
│           SQLite 数据库              │
│    附件文件存储 · OCR 引擎           │
└─────────────────────────────────────┘
```

- **后端**: Python 3.10+ / FastAPI / SQLAlchemy / SQLite
- **前端**: Vue 3 / Vite / Element Plus / Vue Router
- **OCR**: Tesseract-OCR + PyMuPDF + pdfplumber
- **认证**: JWT (python-jose) + bcrypt 密码哈希

## 🚀 快速开始

### 30 秒启动（Windows）

```bash
# 1. 确保已安装 Python 3.10+
# 2. 双击 start.bat
# 3. 浏览器打开 http://localhost:8000
# 默认管理员: admin / admin123
```

### 一行命令启动（Linux）

```bash
cd /opt/contract-archive && bash deploy.sh
```

### Docker 启动

```bash
docker run -d -p 8000:8000 -e SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") contract-archive
```

> 📖 详细部署指南请查看 [部署方案.md](部署方案.md)

## 📸 界面预览

> 截图待补充 — 欢迎贡献！

## ⚙️ 部署方式

| 方式 | 适用场景 | 文档 |
|------|---------|------|
| 🪟 Windows 直接部署 | 单机使用 / 测试环境 | [start.bat](start.bat) |
| 🐧 Linux 部署 | 生产环境服务器 | [deploy.sh](deploy.sh) |
| 🐳 Docker 部署 | 容器化 / 云服务 | [Dockerfile](Dockerfile) |

## 🔒 安全配置

1. **首次登录务必修改默认密码** `admin / admin123`
2. 生产环境设置强 `SECRET_KEY`：`python -c "import secrets; print(secrets.token_hex(32))"`
3. 配置 `ENVIRONMENT=production` 启用安全模式
4. 建议通过 Nginx 反向代理 + HTTPS 对外提供服务

## 📋 环境要求

| 组件 | 要求 |
|------|------|
| Python | 3.10+ |
| 内存 | ≥ 1GB（OCR 识别建议 ≥ 2GB） |
| 磁盘 | ≥ 10GB |
| Tesseract OCR | 可选（用于扫描件识别） |

## 📄 License

[MIT](LICENSE) © 2024

---

<p align="center">
  <sub>如果这个项目对你有帮助，欢迎 ⭐ Star 支持！</sub>
</p>
