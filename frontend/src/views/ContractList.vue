<template>
  <div class="contract-list">
    <!-- 搜索筛选区 -->
    <div class="card-container">
      <!-- 全局模糊搜索 -->
      <div class="global-search">
        <el-input
          v-model="searchForm.keyword"
          placeholder="全局搜索：输入任意关键词，覆盖编号/名称/公司/金额/部门/备注..."
          clearable
          @keyup.enter="handleSearch"
          @clear="handleSearch"
          size="large"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>

      <!-- 高级筛选 -->
      <el-collapse v-model="showAdvanced" class="advanced-filters">
        <el-collapse-item title="高级筛选" name="1">
          <el-form :inline="true" :model="searchForm" class="search-form">
            <el-form-item label="合同编号">
              <el-input v-model="searchForm.contract_no" placeholder="编号模糊搜索" clearable style="width: 160px" />
            </el-form-item>
            <el-form-item label="合同名称">
              <el-input v-model="searchForm.contract_name" placeholder="名称模糊搜索" clearable style="width: 160px" />
            </el-form-item>
            <el-form-item label="对方公司">
              <el-input v-model="searchForm.counterparty" placeholder="对方公司模糊" clearable style="width: 160px" />
            </el-form-item>
            <el-form-item label="金额">
              <el-input v-model="searchForm.amount" placeholder="含关键词即可" clearable style="width: 140px" />
            </el-form-item>
            <el-form-item label="合同类型">
              <el-select v-model="searchForm.contract_type" placeholder="请选择" clearable style="width: 120px">
                <el-option label="采购" value="采购" />
                <el-option label="销售" value="销售" />
                <el-option label="其他" value="其他" />
              </el-select>
            </el-form-item>
            <el-form-item label="我方公司">
              <el-select v-model="searchForm.company_id" placeholder="请选择" clearable style="width: 180px">
                <el-option
                  v-for="company in companyList"
                  :key="company.id"
                  :label="company.name"
                  :value="company.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="部门">
              <el-input v-model="searchForm.department" placeholder="部门名称" clearable style="width: 140px" />
            </el-form-item>
            <el-form-item label="提交日期">
              <el-date-picker
                v-model="dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                style="width: 240px"
              />
            </el-form-item>
          </el-form>
        </el-collapse-item>
      </el-collapse>

      <div class="search-actions">
        <el-button type="primary" @click="handleSearch">
          <el-icon><Search /></el-icon>
          搜索
        </el-button>
        <el-button @click="handleReset">
          <el-icon><Refresh /></el-icon>
          重置
        </el-button>
        <el-button type="success" @click="handleExport">
          <el-icon><Download /></el-icon>
          导出 Excel
        </el-button>
        <el-button type="info" @click="handleBatchImport">
          <el-icon><Upload /></el-icon>
          批量导入
        </el-button>
      </div>
    </div>

    <!-- 合同列表 -->
    <div class="card-container">
      <el-table
        v-loading="loading"
        :data="contractList"
        stripe
        border
        @row-click="handleRowClick"
        @sort-change="handleSortChange"
        style="cursor: pointer"
      >
        <el-table-column prop="contract_no" label="合同编号" width="150" sortable="custom" />
        <el-table-column prop="contract_name" label="合同名称" min-width="200" show-overflow-tooltip sortable="custom" />
        <el-table-column prop="contract_type" label="类型" width="80" sortable="custom">
          <template #default="{ row }">
            <el-tag :type="getTypeColor(row.contract_type)" size="small">
              {{ row.contract_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="company_name" label="我方公司" width="180" show-overflow-tooltip />
        <el-table-column prop="counterparty" label="对方公司" width="180" show-overflow-tooltip sortable="custom" />
        <el-table-column prop="submit_date" label="提交日期" width="110" sortable="custom" />
        <el-table-column prop="amount" label="金额" width="120" sortable="custom" />
        <el-table-column prop="department" label="部门" width="100" sortable="custom" />
        <el-table-column label="附件" width="70" align="center">
          <template #default="{ row }">
            <span
              v-if="row.attachment_count > 0"
              class="attachment-badge"
              title="点击预览附件"
              @click.stop="handleAttachmentClick(row)"
            >
              <el-icon><Paperclip /></el-icon>
              {{ row.attachment_count }}
            </span>
            <span v-else style="color: #C0C4CC">--</span>
          </template>
        </el-table-column>
        <el-table-column prop="handler" label="经办人" width="100" />
        <el-table-column prop="creator_name" label="录入人" width="100" />
        <el-table-column prop="created_at" label="录入时间" width="160" sortable="custom">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag
              :type="row.status === '作废' ? 'danger' : 'success'"
              size="small"
              :effect="row.status === '作废' ? 'light' : 'light'"
            >
              {{ row.status || '有效' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click.stop="viewDetail(row.id)">
              查看
            </el-button>
            <el-button
              v-if="isAdmin"
              :type="row.status === '作废' ? 'success' : 'danger'"
              link
              @click.stop="toggleStatus(row)"
            >
              {{ row.status === '作废' ? '恢复' : '作废' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </div>

    <!-- 附件选择弹窗 -->
    <el-dialog v-model="showAttDialog" title="选择要预览的附件" width="480px" :close-on-click-modal="true">
      <el-table :data="attDialogList" @row-click="previewAttFromDialog" max-height="400" highlight-current-row style="cursor: pointer">
        <el-table-column label="附件名" prop="file_name" min-width="260" show-overflow-tooltip />
        <el-table-column label="类型" width="80">
          <template #default="{ row: att }">
            <el-tag size="small" :type="att.file_type === 'pdf' ? 'danger' : 'success'">{{ att.file_type.toUpperCase() }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showAttDialog = false">取消</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入对话框 -->
    <el-dialog v-model="showImportDialog" title="批量导入合同" width="800px" @close="resetImport">
      <el-form :model="importForm" label-width="100px">
        <el-form-item label="Excel文件" required>
          <el-upload
            ref="excelUploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".xlsx,.xls"
            :on-change="handleExcelChange"
            :on-remove="() => importForm.excelFile = null"
          >
            <el-button type="primary">选择 Excel 文件</el-button>
            <template #tip>
              <div class="el-upload__tip">
                第一行为表头，支持列名：合同编号、合同名称、合同类型、对方公司、提交日期、部门、金额 等
              </div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="PDF附件">
          <el-upload
            ref="pdfUploadRef"
            :auto-upload="false"
            multiple
            accept=".pdf"
            :on-change="handlePdfChange"
          >
            <el-button type="default">选择 PDF 文件（可选）</el-button>
            <template #tip>
              <div class="el-upload__tip">
                文件名中含合同编号的会自动关联，其余列在未匹配列表中
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>

      <!-- 导入结果 -->
      <div v-if="importResult" class="import-result">
        <el-alert
          :title="`导入完成：成功 ${importResult.success} 条，跳过 ${importResult.skipped} 条，共 ${importResult.total} 条`"
          :type="importResult.errors.length > 0 ? 'warning' : 'success'"
          :closable="false"
        />
        <div v-if="importResult.errors.length > 0" class="import-errors">
          <p class="error-title">跳过详情（{{ importResult.errors.length }} 条）：</p>
          <el-table :data="importResult.errors" border size="small" max-height="300" style="margin-top: 8px">
            <el-table-column label="行号" width="70" prop="row" />
            <el-table-column label="类型" width="120">
              <template #default="{ row: err }">
                <el-tag :type="getErrorTagType(err.type)" size="small">{{ getErrorTypeLabel(err.type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="合同编号" width="140" prop="contract_no" />
            <el-table-column label="附件名" width="180" prop="pdf_name" show-overflow-tooltip />
            <el-table-column label="已存在位置" min-width="200">
              <template #default="{ row: err }">
                <template v-if="err.existing_id">
                  合同ID: {{ err.existing_id }}<br/>
                  <span class="existing-detail">{{ err.existing_name }}</span><br/>
                  <span class="existing-detail">{{ err.existing_counterparty }} · {{ err.existing_department }}</span>
                </template>
                <template v-else-if="err.duplicate_source">
                  <span class="existing-detail">{{ err.duplicate_source }}</span>
                </template>
                <template v-else>
                  <span class="existing-detail">-</span>
                </template>
              </template>
            </el-table-column>
            <el-table-column label="说明" min-width="200" prop="message" show-overflow-tooltip />
          </el-table>
        </div>
        <div v-if="importResult.unmatched_pdfs?.length > 0" class="unmatched-pdfs">
          <p class="error-title">未匹配的 PDF 文件：</p>
          <ul>
            <li v-for="(pdf, idx) in importResult.unmatched_pdfs" :key="idx">{{ pdf }}</li>
          </ul>
        </div>
      </div>

      <template #footer>
        <el-button @click="showImportDialog = false">关闭</el-button>
        <el-button type="primary" :loading="importing" @click="handleImportSubmit" :disabled="!importForm.excelFile">
          开始导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Download, Upload, Paperclip } from '@element-plus/icons-vue'
import { getContractList, exportContracts, getCompanyList, batchImport, getContractAttachments } from '@/api/contract'
import { saveAsDialog } from '@/utils/saveAs'
import { useAuthStore } from '@/stores/auth'
import api from '@/api/index'

const router = useRouter()
const authStore = useAuthStore()
const isAdmin = authStore.isAdmin

// 数据
const loading = ref(false)
const contractList = ref([])
const companyList = ref([])
const dateRange = ref([])
const showAdvanced = ref([])

// 搜索表单
const searchForm = reactive({
  keyword: '',
  contract_no: '',
  contract_name: '',
  counterparty: '',
  amount: '',
  contract_type: '',
  company_id: null,
  department: '',
  sort_by: 'created_at',
  sort_order: 'desc'
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 批量导入
const showImportDialog = ref(false)
const importing = ref(false)
const importResult = ref(null)
const importForm = reactive({
  excelFile: null,
  pdfFiles: []
})
const excelUploadRef = ref(null)
const pdfUploadRef = ref(null)

// 附件预览弹窗
const showAttDialog = ref(false)
const attDialogList = ref([])

// 加载数据
async function loadData() {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      sort_by: searchForm.sort_by,
      sort_order: searchForm.sort_order
    }

    // 传递非空的搜索字段
    for (const key of ['keyword', 'contract_no', 'contract_name', 'counterparty', 'amount', 'contract_type', 'department']) {
      if (searchForm[key]) params[key] = searchForm[key]
    }
    if (searchForm.company_id) params.company_id = searchForm.company_id
    if (dateRange.value?.length === 2) {
      params.submit_date_from = dateRange.value[0]
      params.submit_date_to = dateRange.value[1]
    }

    const response = await getContractList(params)
    contractList.value = response.data.items
    pagination.total = response.data.total || 0
  } catch (error) {
    console.error('加载失败', error)
  } finally {
    loading.value = false
  }
}

// 加载公司列表
async function loadCompanies() {
  try {
    const response = await getCompanyList()
    companyList.value = response.data
  } catch (error) {
    console.error('加载公司列表失败', error)
  }
}

// 排序
function handleSortChange({ prop, order }) {
  if (prop) {
    searchForm.sort_by = prop
    searchForm.sort_order = order === 'ascending' ? 'asc' : 'desc'
  } else {
    searchForm.sort_by = 'created_at'
    searchForm.sort_order = 'desc'
  }
  loadData()
}

// 搜索
function handleSearch() {
  pagination.page = 1
  loadData()
}

// 重置
function handleReset() {
  Object.keys(searchForm).forEach(key => {
    if (['company_id'].includes(key)) {
      searchForm[key] = null
    } else if (['sort_by', 'sort_order'].includes(key)) {
      searchForm['sort_by'] = 'created_at'
      searchForm['sort_order'] = 'desc'
    } else {
      searchForm[key] = ''
    }
  })
  dateRange.value = []
  handleSearch()
}

// 导出
async function handleExport() {
  try {
    const params = {}
    for (const key of ['keyword', 'contract_type', 'department', 'counterparty']) {
      if (searchForm[key]) params[key] = searchForm[key]
    }
    if (searchForm.company_id) params.company_id = searchForm.company_id
    if (dateRange.value?.length === 2) {
      params.submit_date_from = dateRange.value[0]
      params.submit_date_to = dateRange.value[1]
    }

    const response = await exportContracts(params)
    const defaultName = `合同列表_${new Date().toISOString().split('T')[0]}.xlsx`
    const blob = new Blob([response.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })

    const saved = await saveAsDialog(blob, {
      suggestedName: defaultName,
      mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      types: [{
        description: 'Excel 工作簿',
        accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] },
      }],
    })

    if (saved) {
      ElMessage.success('导出成功')
    }
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

// 批量导入
function handleBatchImport() {
  importResult.value = null
  showImportDialog.value = true
}

function handleExcelChange(file) {
  importForm.excelFile = file.raw
}

function handlePdfChange(file, files) {
  importForm.pdfFiles = files.map(f => f.raw)
}

function resetImport() {
  importForm.excelFile = null
  importForm.pdfFiles = []
  importResult.value = null
}

// 批量导入错误类型映射
function getErrorTypeLabel(type) {
  const map = {
    'missing_field': '缺少必填字段',
    'contract_no_duplicate': '编号重复',
    'attachment_duplicate': '附件重复',
    'attachment_save_failed': '附件保存失败',
    'create_failed': '创建失败'
  }
  return map[type] || type
}

function getErrorTagType(type) {
  const map = {
    'missing_field': 'danger',
    'contract_no_duplicate': 'warning',
    'attachment_duplicate': 'warning',
    'attachment_save_failed': 'danger',
    'create_failed': 'danger'
  }
  return map[type] || 'info'
}

async function handleImportSubmit() {
  if (!importForm.excelFile) {
    ElMessage.warning('请选择 Excel 文件')
    return
  }

  importing.value = true
  try {
    const formData = new FormData()
    formData.append('excel_file', importForm.excelFile)
    for (const pdf of importForm.pdfFiles) {
      formData.append('pdf_files', pdf)
    }

    const response = await batchImport(formData)
    importResult.value = response.data
    if (response.data.success > 0) {
      loadData()
    }
  } catch (error) {
    // 错误已在拦截器处理
  } finally {
    importing.value = false
  }
}

// 查看详情
function viewDetail(id) {
  router.push(`/contracts/${id}`)
}

// 切换合同状态（有效↔作废），仅管理员可用
async function toggleStatus(row) {
  const newStatus = row.status === '作废' ? '有效' : '作废'
  const actionText = newStatus === '作废' ? '将该合同标记为作废' : '恢复该合同为有效'
  try {
    await ElMessageBox.confirm(
      `确定要${actionText}吗？`,
      '更改合同状态',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: newStatus === '作废' ? 'warning' : 'success'
      }
    )
    await api.put(`/contracts/${row.id}/status`, { status: newStatus })
    row.status = newStatus
    ElMessage.success(`已${actionText}`)
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('操作失败：' + (e.response?.data?.detail || e.message))
    }
  }
}

// 点击附件徽章 → 查附件列表 → 1个直接预览，多个弹窗选
async function handleAttachmentClick(row) {
  if (!row.attachment_count) return
  try {
    const resp = await getContractAttachments(row.id)
    const atts = resp.data || []
    if (atts.length === 0) return

    if (atts.length === 1) {
      // 只有1个附件 → 直接新标签页预览
      const token = localStorage.getItem('token')
      window.open(`/api/contracts/${row.id}/attachments/${atts[0].id}/preview?token=${token}`, '_blank')
    } else {
      // 多个附件 → 弹窗让用户选择
      attDialogList.value = atts.map(a => ({ ...a, contractId: row.id }))
      showAttDialog.value = true
    }
  } catch (e) {
    console.error('获取附件列表失败', e)
  }
}

// 从弹窗中选择附件预览
function previewAttFromDialog(att) {
  const token = localStorage.getItem('token')
  window.open(`/api/contracts/${att.contractId}/attachments/${att.id}/preview?token=${token}`, '_blank')
  showAttDialog.value = false
}

// 行点击
function handleRowClick(row) {
  viewDetail(row.id)
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

onMounted(() => {
  loadData()
  loadCompanies()
})
</script>

<style scoped>
.global-search {
  margin-bottom: 12px;
}

.advanced-filters {
  margin-bottom: 12px;
}

.search-form {
  margin-bottom: 0;
}

.search-actions {
  display: flex;
  gap: 8px;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.import-result {
  margin-top: 16px;
}

.import-errors,
.unmatched-pdfs {
  margin-top: 12px;
}

.import-errors {
  max-height: 480px;
  overflow: auto;
}

.unmatched-pdfs {
  padding: 12px;
  background: #fdf6ec;
  border-radius: 6px;
  font-size: 13px;
}

.existing-detail {
  font-size: 12px;
  color: #909399;
}

.error-title {
  font-weight: 500;
  margin-bottom: 4px;
  color: #f56c6c;
}

.unmatched-pdfs ul {
  margin: 0;
  padding-left: 18px;
}

.unmatched-pdfs li {
  color: #606266;
  line-height: 1.6;
}

.attachment-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: #409EFF;
  font-weight: 500;
  font-size: 13px;
  cursor: pointer;
}
</style>
