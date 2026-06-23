/**
 * 合同相关 API
 */
import api from './index'

// 获取合同列表
export function getContractList(params) {
  return api.get('/contracts', { params })
}

// 获取合同详情
export function getContract(id) {
  return api.get(`/contracts/${id}`)
}

// 创建合同
export function createContract(data) {
  return api.post('/contracts', data)
}

// 更新合同
export function updateContract(id, data) {
  return api.put(`/contracts/${id}`, data)
}

// 更新备忘录（单独接口，任何人可改）
export function updateMemo(id, memo) {
  return api.put(`/contracts/${id}/memo`, { memo })
}

// 删除合同
export function deleteContract(id) {
  return api.delete(`/contracts/${id}`)
}

// 导出 Excel
export function exportContracts(params) {
  return api.get('/contracts/export', { params, responseType: 'blob' })
}

// 批量导入合同
export function batchImport(formData) {
  return api.post('/contracts/batch-import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  })
}

// 获取合同附件列表（轻量，供列表页预览用）
export function getContractAttachments(contractId) {
  return api.get(`/contracts/${contractId}/attachments`)
}

// 上传附件
export function uploadAttachments(contractId, files) {
  const formData = new FormData()
  files.forEach(file => {
    formData.append('files', file)
  })
  return api.post(`/contracts/${contractId}/attachments`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 上传附件（强制替换同名文件）
export function uploadAttachmentsWithReplace(contractId, files) {
  const formData = new FormData()
  files.forEach(file => {
    formData.append('files', file)
  })
  return api.post(`/contracts/${contractId}/attachments?replace_existing=true`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 上传附件（指定冲突处理模式: skip | replace | add_new）
export function uploadAttachmentsWithMode(contractId, files, mode) {
  const formData = new FormData()
  files.forEach(file => {
    formData.append('files', file)
  })
  return api.post(`/contracts/${contractId}/attachments?mode=${mode}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 删除附件
export function deleteAttachment(contractId, attachmentId) {
  return api.delete(`/contracts/${contractId}/attachments/${attachmentId}`)
}

// 获取公司列表
export function getCompanyList() {
  return api.get('/contracts/companies')
}

// 创建公司
export function createCompany(data) {
  return api.post('/contracts/companies', data)
}

// 更新公司
export function updateCompany(id, data) {
  return api.put(`/contracts/companies/${id}`, data)
}

// 删除公司
export function deleteCompany(id) {
  return api.delete(`/contracts/companies/${id}`)
}

// 备份导出（管理员）
export function backupContracts(params) {
  return api.post('/admin/backup', null, {
    params,
    responseType: 'blob',
    timeout: 300000  // 大文件备份5分钟超时
  })
}

// 恢复导入（管理员）
export function restoreBackup(file) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/admin/restore', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000  // 大文件恢复5分钟超时
  })
}

// OCR 识别（Tesseract 处理扫描件可能很慢，超时设 3 分钟）
export function ocrRecognize(file) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/contracts/ocr', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,  // 3 分钟，Tesseract 处理多页扫描件需要较长时间
  })
}

// 用户管理
export function getUserList() {
  return api.get('/auth/users')
}

export function createUser(data) {
  return api.post('/auth/register', data)
}

export function updateUser(id, data) {
  return api.put(`/auth/users/${id}`, data)
}

export function deleteUser(id) {
  return api.delete(`/auth/users/${id}`)
}
