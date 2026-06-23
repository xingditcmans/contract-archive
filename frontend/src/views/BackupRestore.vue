<template>
  <div class="backup-restore">
    <!-- 备份导出 -->
    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon size="20"><Download /></el-icon>
          <span>数据备份导出</span>
        </div>
      </template>

      <el-form :inline="true" :model="backupForm" class="backup-form">
        <el-form-item label="筛选年份">
          <el-select v-model="backupForm.year" placeholder="全部年份" clearable style="width: 150px">
            <el-option
              v-for="y in availableYears"
              :key="y"
              :label="String(y)"
              :value="y"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="合同类型">
          <el-select v-model="backupForm.contract_type" placeholder="全部类型" clearable style="width: 150px">
            <el-option label="采购" value="采购" />
            <el-option label="销售" value="销售" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-checkbox v-model="backupForm.all" @change="onAllChange">
            全选（忽略筛选条件）
          </el-checkbox>
        </el-form-item>
      </el-form>

      <div class="action-row">
        <el-button type="primary" :icon="Download" :loading="backingUp" @click="handleBackup">
          {{ backingUp ? '正在打包...' : '导出备份' }}
        </el-button>
        <span class="hint-text">
          导出为 ZIP 压缩包，包含合同数据（JSON）和附件（PDF），可用于灾备或系统迁移
        </span>
      </div>

      <el-alert
        v-if="backupError"
        :title="backupError"
        type="error"
        show-icon
        :closable="true"
        style="margin-top: 15px"
        @close="backupError = ''"
      />
    </el-card>

    <!-- 恢复导入 -->
    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon size="20"><Upload /></el-icon>
          <span>数据恢复导入</span>
        </div>
      </template>

      <el-upload
        ref="uploadRef"
        class="upload-area"
        drag
        :auto-upload="false"
        :limit="1"
        accept=".zip"
        :on-change="onFileChange"
        :on-remove="onFileRemove"
        :file-list="fileList"
      >
        <el-icon class="upload-icon" size="48"><FolderAdd /></el-icon>
        <div class="upload-text">
          <p>将备份 ZIP 文件拖到此处，或<em>点击上传</em></p>
          <p class="upload-hint">仅支持 .zip 格式的备份文件</p>
        </div>
      </el-upload>

      <div class="action-row">
        <el-button
          type="warning"
          :icon="Upload"
          :loading="restoring"
          :disabled="!selectedFile"
          @click="handleRestore"
        >
          {{ restoring ? '正在恢复...' : '导入恢复' }}
        </el-button>
      </div>

      <!-- 恢复结果 -->
      <div v-if="restoreResult" class="restore-result">
        <el-divider />
        <h4>恢复结果</h4>
        <el-row :gutter="20" class="result-stats">
          <el-col :span="6">
            <el-statistic title="总计" :value="restoreResult.total" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="已创建" :value="restoreResult.created">
              <template #suffix>
                <el-tag type="success" size="small">新建</el-tag>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="6">
            <el-statistic title="已覆盖" :value="restoreResult.overwritten">
              <template #suffix>
                <el-tag type="warning" size="small">覆盖</el-tag>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="6">
            <el-statistic title="附件恢复" :value="restoreResult.attachments_restored" />
          </el-col>
        </el-row>

        <!-- 错误明细 -->
        <div v-if="restoreResult.errors && restoreResult.errors.length > 0" style="margin-top: 20px">
          <h5>错误明细（{{ restoreResult.errors.length }} 条）</h5>
          <el-table :data="restoreResult.errors" border stripe size="small" max-height="300">
            <el-table-column prop="contract_no" label="合同编号" width="160" />
            <el-table-column prop="contract_name" label="合同名称" width="200" show-overflow-tooltip />
            <el-table-column label="类型" width="120">
              <template #default="{ row }">
                <el-tag :type="getErrorTypeTag(row.type)" size="small">
                  {{ getErrorLabel(row.type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="说明" show-overflow-tooltip />
          </el-table>
        </div>
      </div>

      <el-alert
        v-if="restoreError"
        :title="restoreError"
        type="error"
        show-icon
        :closable="true"
        style="margin-top: 15px"
        @close="restoreError = ''"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Upload, FolderAdd } from '@element-plus/icons-vue'
import { backupContracts, restoreBackup, getContractList } from '@/api/contract'
import { saveAsDialog } from '@/utils/saveAs'

/* ==================== 备份导出 ==================== */
const backupForm = ref({
  year: null,
  contract_type: '',
  all: false,
})
const backingUp = ref(false)
const backupError = ref('')

// 可用年份：从合同数据中提取
const availableYears = ref([])

onMounted(async () => {
  try {
    // 获取所有合同的年份范围（取第一页大一点获取年份分布）
    const res = await getContractList({ page: 1, page_size: 100 })
    const years = new Set()
    if (res.data) {
      res.data.forEach(c => {
        if (c.submit_date) {
          const y = parseInt(c.submit_date.substring(0, 4))
          if (y) years.add(y)
        }
      })
    }
    availableYears.value = [...years].sort((a, b) => b - a)
  } catch {
    // 获取年份失败不阻塞
  }
})

function onAllChange(val) {
  if (val) {
    backupForm.value.year = null
    backupForm.value.contract_type = ''
  }
}

async function handleBackup() {
  backingUp.value = true
  backupError.value = ''

  try {
    const params = {}
    if (!backupForm.value.all) {
      if (backupForm.value.year) params.year = backupForm.value.year
      if (backupForm.value.contract_type) params.contract_type = backupForm.value.contract_type
    } else {
      params.all = true
    }

    const res = await backupContracts(params)

    // 从响应头获取统计信息
    const contractCount = res.headers['x-backup-contracts'] || '?'
    const attachmentCount = res.headers['x-backup-attachments'] || '?'

    // 从 Content-Disposition 取默认文件名
    const disposition = res.headers['content-disposition'] || ''
    const match = disposition.match(/filename="?([^";\n]+)"?/)
    const defaultName = match ? match[1] : 'contract_backup.zip'

    // 弹出保存对话框，用户可选择路径和修改文件名
    const blob = new Blob([res.data], { type: 'application/zip' })
    const saved = await saveAsDialog(blob, {
      suggestedName: defaultName,
      mimeType: 'application/zip',
      types: [{
        description: 'ZIP 压缩包',
        accept: { 'application/zip': ['.zip'] },
      }],
    })

    if (saved) {
      ElMessage.success(
        `备份导出成功！包含 ${contractCount} 份合同、${attachmentCount} 个附件`
      )
    }
    // 用户取消则静默
  } catch (err) {
    if (err.response?.status === 404) {
      backupError.value = '没有符合条件的合同数据，请调整筛选条件'
    } else {
      backupError.value = err.response?.data?.detail || '备份导出失败'
    }
  } finally {
    backingUp.value = false
  }
}

/* ==================== 恢复导入 ==================== */
const uploadRef = ref(null)
const fileList = ref([])
const selectedFile = ref(null)
const restoring = ref(false)
const restoreError = ref('')
const restoreResult = ref(null)

function onFileChange(file) {
  selectedFile.value = file.raw
  fileList.value = [file]
  restoreResult.value = null
  restoreError.value = ''
}

function onFileRemove() {
  selectedFile.value = null
  fileList.value = []
  restoreResult.value = null
  restoreError.value = ''
}

async function handleRestore() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择备份文件')
    return
  }

  await ElMessageBox.confirm(
    '⚠️ 恢复操作将导入备份中的所有合同和附件数据。\n已存在的合同将被覆盖更新（含附件替换），不会跳过。\n此操作不可撤销，确定要继续吗？',
    '确认恢复（覆盖模式）',
    {
      confirmButtonText: '确定覆盖',
      cancelButtonText: '取消',
      type: 'warning',
    }
  )

  restoring.value = true
  restoreError.value = ''
  restoreResult.value = null

  try {
    const res = await restoreBackup(selectedFile.value)
    restoreResult.value = res.data

    if (res.data.created > 0 || res.data.overwritten > 0) {
      const parts = []
      if (res.data.created > 0) parts.push(`新建 ${res.data.created} 份合同`)
      if (res.data.overwritten > 0) parts.push(`覆盖 ${res.data.overwritten} 份合同`)
      ElMessage.success(
        `恢复完成：${parts.join('，')}，${res.data.attachments_restored} 个附件`
      )
    } else {
      ElMessage.warning('没有合同数据被导入')
    }
  } catch (err) {
    restoreError.value = err.response?.data?.detail || '恢复导入失败'
    ElMessage.error(restoreError.value)
  } finally {
    restoring.value = false
  }
}

function getErrorLabel(type) {
  const map = {
    create_failed: '创建失败',
    attachment_missing: '附件缺失',
    attachment_save_failed: '附保存失败',
  }
  return map[type] || type
}

function getErrorTypeTag(type) {
  const map = {
    create_failed: 'danger',
    attachment_missing: 'info',
    attachment_save_failed: 'danger',
  }
  return map[type] || 'info'
}
</script>

<style scoped>
.backup-restore {
  max-width: 900px;
  margin: 0 auto;
}

.section-card {
  margin-bottom: 24px;
  border-radius: 8px;
}

.section-card :deep(.el-card__header) {
  background-color: #fafafa;
  padding: 12px 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.backup-form {
  margin-bottom: 0;
}

.action-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 8px;
}

.hint-text {
  color: #909399;
  font-size: 13px;
}

/* 上传区域 */
.upload-area {
  width: 100%;
}

.upload-area :deep(.el-upload-dragger) {
  padding: 30px;
}

.upload-icon {
  color: #c0c4cc;
}

.upload-text p {
  margin: 8px 0 0;
  color: #606266;
  font-size: 14px;
}

.upload-text em {
  color: #409EFF;
  font-style: normal;
}

.upload-hint {
  color: #c0c4cc !important;
  font-size: 12px !important;
}

/* 恢复结果 */
.restore-result h4 {
  margin: 0 0 12px;
  font-size: 16px;
  color: #303133;
}

.restore-result h5 {
  margin: 0 0 8px;
  font-size: 14px;
  color: #606266;
}

.result-stats {
  margin-bottom: 10px;
}
</style>
