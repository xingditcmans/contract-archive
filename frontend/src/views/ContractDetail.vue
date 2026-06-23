<template>
  <div class="contract-detail">
    <div v-loading="loading">
      <!-- 基本信息卡片 -->
      <div class="card-container">
        <div class="detail-header">
          <h2 class="page-title">合同详情</h2>
          <div class="detail-actions">
            <el-button
              v-if="canEdit"
              type="primary"
              @click="handleEdit"
            >
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button
              v-if="isAdmin"
              type="danger"
              @click="handleDelete"
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </div>
        </div>

        <el-descriptions :column="2" border class="detail-descriptions">
          <el-descriptions-item label="合同编号">
            {{ contract.contract_no }}
          </el-descriptions-item>
          <el-descriptions-item label="合同类型">
            <el-tag :type="getTypeColor(contract.contract_type)">
              {{ contract.contract_type }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="合同名称" :span="2">
            {{ contract.contract_name }}
          </el-descriptions-item>
          <el-descriptions-item label="我方公司">
            {{ contract.company_name || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="对方公司">
            {{ contract.counterparty }}
          </el-descriptions-item>
          <el-descriptions-item label="提交日期">
            {{ contract.submit_date }}
          </el-descriptions-item>
          <el-descriptions-item label="有效期至">
            {{ contract.valid_until || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="合同金额">
            {{ contract.amount || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="纸质份数">
            {{ contract.paper_copies || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="所属部门">
            {{ contract.department }}
          </el-descriptions-item>
          <el-descriptions-item label="经办人">
            {{ contract.handler || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="录入人">
            {{ contract.creator_name }}
          </el-descriptions-item>
          <el-descriptions-item label="录入时间">
            {{ formatDate(contract.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="最后更新">
            {{ formatDate(contract.updated_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="合同状态">
            <el-tag
              :type="contract.status === '作废' ? 'danger' : 'success'"
              size="small"
            >
              {{ contract.status || '有效' }}
            </el-tag>
            <el-button
              v-if="isAdmin"
              :type="contract.status === '作废' ? 'success' : 'warning'"
              size="small"
              style="margin-left: 12px"
              @click="toggleStatus"
            >
              {{ contract.status === '作废' ? '恢复有效' : '标记作废' }}
            </el-button>
          </el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">
            {{ contract.remarks || '-' }}
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <!-- 附件卡片 -->
      <div class="card-container">
        <div class="section-header">
          <h3>合同附件</h3>
          <el-button
            v-if="canEdit"
            type="primary"
            size="small"
            @click="showUploadDialog = true"
          >
            <el-icon><Upload /></el-icon>
            上传附件
          </el-button>
        </div>

        <el-table
          v-if="contract.attachments?.length"
          :data="contract.attachments"
          border
        >
          <el-table-column prop="file_name" label="文件名" />
          <el-table-column prop="file_type" label="类型" width="80">
            <template #default="{ row }">
              <el-tag size="small">{{ row.file_type.toUpperCase() }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="file_size" label="大小" width="120">
            <template #default="{ row }">
              {{ formatFileSize(row.file_size) }}
            </template>
          </el-table-column>
          <el-table-column prop="uploader_name" label="上传人" width="100" />
          <el-table-column prop="uploaded_at" label="上传时间" width="160">
            <template #default="{ row }">
              {{ formatDate(row.uploaded_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="isPreviewable(row)"
                type="primary"
                link
                @click="handlePreview(row)"
              >
                <el-icon><View /></el-icon>
                预览
              </el-button>
              <el-button
                type="primary"
                link
                @click="handleDownload(row)"
              >
                <el-icon><Download /></el-icon>
                下载
              </el-button>
              <el-button
                v-if="isAdmin"
                type="danger"
                link
                @click="handleDeleteAttachment(row)"
              >
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-else description="暂无附件" />
      </div>

      <!-- 备忘录卡片（任何人可随时修改） -->
      <div class="card-container memo-card">
        <div class="section-header">
          <h3>
            <el-icon><Document /></el-icon>
            备忘录
            <span class="memo-tip">（任何人都可以随时修改）</span>
          </h3>
        </div>

        <el-input
          v-model="memo"
          type="textarea"
          :rows="6"
          placeholder="可随时记录合同相关备注，如：2024-01-15 正本被XXX借走，未归还..."
          @blur="saveMemo"
        />

        <div class="memo-actions">
          <el-button type="primary" size="small" @click="saveMemo">
            保存备忘录
          </el-button>
          <span class="memo-status" v-if="memoSaved">
            <el-icon color="#67C23A"><Check /></el-icon>
            已保存
          </span>
        </div>
      </div>
    </div>

    <!-- 附件冲突对话框 -->
    <el-dialog v-model="showConflictDialog" title="⚠️ 同名附件冲突" width="650px" :close-on-click-modal="false">
      <el-alert
        title="以下文件已存在同名附件，请选择处理方式"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <el-table :data="conflictFiles" border size="small">
        <el-table-column label="附件名" prop="filename" min-width="200" />
        <el-table-column label="已有附件" min-width="200">
          <template #default="{ row }">
            <div class="conflict-existing">
              <div>大小：{{ formatConflictSize(row.existing_size) }}</div>
              <div>上传时间：{{ row.existing_uploaded_at ? formatDate(row.existing_uploaded_at) : '-' }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="新文件" min-width="100">
          <template #default="{ row }">
            {{ formatConflictSize(row.new_size) }}
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="handleConflictCancel">取消</el-button>
        <el-button @click="handleConflictSkip">跳过（只上传不冲突的）</el-button>
        <el-button type="danger" @click="handleConflictReplace">替换旧文件</el-button>
        <el-button type="success" @click="handleConflictAddNew">保留旧文件，新增一份</el-button>
      </template>
    </el-dialog>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传附件" width="500px">
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :file-list="uploadFileList"
        :on-change="handleUploadChange"
        :on-remove="handleUploadRemove"
        multiple
        accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
      >
        <el-button type="primary">
          <el-icon><Upload /></el-icon>
          选择文件
        </el-button>
      </el-upload>

      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">
          上传
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Edit, Delete, Upload, Download, Document, Check, View
} from '@element-plus/icons-vue'
import {
  getContract, deleteContract, deleteAttachment, updateMemo,
  uploadAttachments, uploadAttachmentsWithReplace, uploadAttachmentsWithMode
} from '@/api/contract'
import { useAuthStore } from '@/stores/auth'
import api from '@/api/index'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loading = ref(false)
const uploading = ref(false)
const contract = ref({})
const memo = ref('')
const memoSaved = ref(false)
const showUploadDialog = ref(false)
const uploadFileList = ref([])
const pendingUploadFiles = ref([])

// 附件冲突对话框
const showConflictDialog = ref(false)
const conflictFiles = ref([])
const conflictResolve = ref(null)  // Promise resolve

const contractId = computed(() => route.params.id)
const isAdmin = computed(() => authStore.isAdmin)
const canEdit = computed(() => {
  return isAdmin.value || authStore.userInfo?.id === contract.value.created_by
})

// 加载数据
async function loadData() {
  loading.value = true
  try {
    const response = await getContract(contractId.value)
    contract.value = response.data
    memo.value = contract.value.memo || ''
  } catch (error) {
    ElMessage.error('加载失败')
    router.back()
  } finally {
    loading.value = false
  }
}

// 编辑
function handleEdit() {
  router.push(`/contracts/${contractId.value}/edit`)
}

// 切换合同状态（仅管理员）
async function toggleStatus() {
  const newStatus = contract.value.status === '作废' ? '有效' : '作废'
  const actionText = newStatus === '作废' ? '将该合同标记为作废' : '恢复该合同为有效'
  try {
    await ElMessageBox.confirm(`确定要${actionText}吗？`, '更改合同状态', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: newStatus === '作废' ? 'warning' : 'success'
    })
    await api.put(`/contracts/${contractId.value}/status`, { status: newStatus })
    contract.value.status = newStatus
    ElMessage.success(`已${actionText}`)
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('操作失败：' + (e.response?.data?.detail || e.message))
    }
  }
}

// 删除
async function handleDelete() {
  try {
    await ElMessageBox.confirm('确定要删除这条合同吗？此操作不可恢复！', '警告', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })

    await deleteContract(contractId.value)
    ElMessage.success('删除成功')
    router.push('/contracts')
  } catch (error) {
    if (error !== 'cancel') {
      // 错误已在拦截器处理
    }
  }
}

// 下载
function handleDownload(attachment) {
  const token = localStorage.getItem('token')
  const url = `/api/contracts/${contractId.value}/attachments/${attachment.id}/download?token=${token}`
  window.open(url, '_blank')
}

// 预览 — 在新标签页打开，方便来回对比
function isPreviewable(attachment) {
  return ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(attachment.file_type)
}

function handlePreview(attachment) {
  const token = localStorage.getItem('token')
  const url = `/api/contracts/${contractId.value}/attachments/${attachment.id}/preview?token=${token}`
  window.open(url, '_blank')
}

// 删除附件
async function handleDeleteAttachment(attachment) {
  try {
    await ElMessageBox.confirm('确定要删除这个附件吗？', '提示')
    await deleteAttachment(contractId.value, attachment.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      // 错误已在拦截器处理
    }
  }
}

// 上传相关
function handleUploadChange(file, files) {
  pendingUploadFiles.value = files.map(f => f.raw)
}

function handleUploadRemove(file, files) {
  pendingUploadFiles.value = files.map(f => f.raw)
}

async function handleUpload() {
  if (pendingUploadFiles.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }

  uploading.value = true
  try {
    const response = await uploadAttachments(contractId.value, pendingUploadFiles.value)
    ElMessage.success(`上传成功 ${response.data.attachments?.length || 0} 个文件`)
    showUploadDialog.value = false
    uploadFileList.value = []
    pendingUploadFiles.value = []
    loadData()
  } catch (error) {
    if (error.response?.status === 409) {
      // 同名附件冲突 → 弹窗让用户四选一
      const data = error.response.data
      conflictFiles.value = data.conflicts || []
      showConflictDialog.value = true

      // 等待用户选择
      try {
        const userMode = await new Promise((resolve, reject) => {
          conflictResolve.value = { resolve, reject }
        })
        // 用户选择了某个模式
        if (userMode === 'cancel') {
          ElMessage.info('已取消上传')
        } else if (userMode === 'skip') {
          const resp2 = await uploadAttachmentsWithMode(contractId.value, pendingUploadFiles.value, 'skip')
          const msg = resp2.data.attachments?.length > 0
            ? `上传 ${resp2.data.attachments.length} 个，跳过 ${resp2.data.skipped?.length || 0} 个冲突文件`
            : `全部 ${resp2.data.skipped?.length || 0} 个文件均已存在，跳过`
          ElMessage.info(msg)
        } else if (userMode === 'replace') {
          await uploadAttachmentsWithMode(contractId.value, pendingUploadFiles.value, 'replace')
          ElMessage.success(`已替换 ${conflictFiles.value.length} 个同名文件`)
        } else if (userMode === 'add_new') {
          const resp3 = await uploadAttachmentsWithMode(contractId.value, pendingUploadFiles.value, 'add_new')
          ElMessage.success(`已新增 ${resp3.data.attachments?.length || 0} 个文件（同名文件自动重命名）`)
        }
        showUploadDialog.value = false
        uploadFileList.value = []
        pendingUploadFiles.value = []
        loadData()
      } catch (userChoice) {
        if (userChoice !== 'cancel') {
          ElMessage.info('已取消上传')
        }
      }
    } else {
      // 其他错误已在拦截器处理
    }
  } finally {
    uploading.value = false
  }
}

// 用户选择"取消"
function handleConflictCancel() {
  conflictResolve.value?.reject('cancel')
  conflictResolve.value = null
  showConflictDialog.value = false
}

// 用户选择"跳过"（只上传不冲突的文件）
function handleConflictSkip() {
  conflictResolve.value?.resolve('skip')
  conflictResolve.value = null
  showConflictDialog.value = false
}

// 用户选择"替换"
function handleConflictReplace() {
  conflictResolve.value?.resolve('replace')
  conflictResolve.value = null
  showConflictDialog.value = false
}

// 用户选择"保留旧文件，新增一份"
function handleConflictAddNew() {
  conflictResolve.value?.resolve('add_new')
  conflictResolve.value = null
  showConflictDialog.value = false
}

// 格式化文件大小
function formatConflictSize(bytes) {
  if (!bytes) return '未知'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// 保存备忘录
async function saveMemo() {
  try {
    await updateMemo(contractId.value, memo.value)
    memoSaved.value = true
    setTimeout(() => {
      memoSaved.value = false
    }, 2000)
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

// 工具函数
function getTypeColor(type) {
  const map = { '采购': 'warning', '销售': 'success', '其他': 'info' }
  return map[type] || 'info'
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

function formatFileSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.detail-actions {
  display: flex;
  gap: 12px;
}

.detail-descriptions {
  margin-top: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.memo-card {
  background: linear-gradient(135deg, #f0f9eb 0%, #e8f5e1 100%);
}

.memo-card h3 {
  color: #67c23a;
}

.memo-tip {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}

.memo-actions {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.memo-status {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #67c23a;
  font-size: 13px;
}

.conflict-existing {
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
}
</style>
