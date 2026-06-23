<template>
  <div class="contract-form">
    <div class="card-container">
      <h2 class="page-title">{{ isEdit ? '编辑合同' : '录入合同' }}</h2>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
        class="contract-form-inner"
      >
        <!-- OCR 识别区域 -->
        <div v-if="!isEdit" class="ocr-section">
          <el-upload
            ref="ocrUploadRef"
            :auto-upload="false"
            :show-file-list="false"
            accept=".pdf,.jpg,.jpeg,.png"
            :on-change="handleOcrFileChange"
          >
            <el-button type="info">
              <el-icon><Upload /></el-icon>
              上传 PDF/图片 OCR 识别
            </el-button>
          </el-upload>
          <span class="ocr-tip">上传合同文件，系统将自动识别文字内容</span>
        </div>

        <!-- 基础信息 -->
        <el-divider content-position="left">基本信息</el-divider>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="合同编号" prop="contract_no">
              <el-input v-model="form.contract_no" placeholder="云之家审批编号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="合同名称" prop="contract_name">
              <el-input v-model="form.contract_name" placeholder="请输入合同名称" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="合同类型" prop="contract_type">
              <el-select v-model="form.contract_type" placeholder="请选择" style="width: 100%">
                <el-option label="采购" value="采购" />
                <el-option label="销售" value="销售" />
                <el-option label="其他" value="其他" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="我方公司" prop="company_id">
              <el-select
                v-model="form.company_id"
                placeholder="请选择"
                style="width: 100%"
                filterable
                @change="handleCompanyChange"
              >
                <el-option
                  v-for="company in companyList"
                  :key="company.id"
                  :label="company.name"
                  :value="company.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="对方公司" prop="counterparty">
          <el-input v-model="form.counterparty" placeholder="请输入对方公司名称" />
        </el-form-item>

        <!-- 日期和金额 -->
        <el-divider content-position="left">日期与金额</el-divider>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="提交日期" prop="submit_date">
              <el-date-picker
                v-model="form.submit_date"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="有效期至" prop="valid_until">
              <el-date-picker
                v-model="form.valid_until"
                type="date"
                placeholder="选填"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="合同金额" prop="amount">
              <el-input v-model="form.amount" placeholder="选填，可填 / 表示框架协议">
                <template #append>元</template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="纸质份数" prop="paper_copies">
              <el-input v-model="form.paper_copies" placeholder="选填" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 人员信息 -->
        <el-divider content-position="left">人员信息</el-divider>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="所属部门" prop="department">
              <el-input v-model="form.department" placeholder="请输入部门名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="经办人" prop="handler">
              <el-input v-model="form.handler" placeholder="选填" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 备注 -->
        <el-divider content-position="left">其他信息</el-divider>

        <el-form-item label="备注" prop="remarks">
          <el-input
            v-model="form.remarks"
            type="textarea"
            :rows="3"
            placeholder="选填"
          />
        </el-form-item>

        <!-- 附件上传 -->
        <el-form-item label="附件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :file-list="fileList"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            multiple
            accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
          >
            <el-button type="primary">
              <el-icon><Upload /></el-icon>
              选择文件
            </el-button>
            <template #tip>
              <div class="el-upload__tip">支持 PDF、图片、Word 格式，单个文件不超过 50MB</div>
            </template>
          </el-upload>
        </el-form-item>

        <!-- OCR 识别结果 -->
        <div v-if="ocrDone" class="ocr-result-panel">
          <el-alert
            :title="ocrResultTitle"
            :type="ocrFilledCount > 0 ? 'success' : 'warning'"
            :closable="false"
          >
            <template v-if="ocrFilledCount > 0">
              <div class="ocr-field-status">
                <span v-for="f in ocrFields" :key="f.key" class="ocr-field-tag" :class="{ filled: f.filled }">
                  {{ f.label }}{{ f.filled ? ' ✓' : ' ✗' }}
                </span>
              </div>
            </template>
            <template v-else>
              <span>未能自动识别关键字段，请查看下方识别文本手动填写</span>
            </template>
          </el-alert>

          <!-- 识别流程状态栏 -->
          <div class="ocr-pipeline-status">
            <span class="pipeline-label">识别流程：</span>
            <span class="pipeline-step" :class="ocrPipelineSteps.ocr.status">
              <span class="step-dot"></span>
              OCR提取{{ ocrPipelineSteps.ocr.note }}
            </span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step" :class="ocrPipelineSteps.regex.status">
              <span class="step-dot"></span>
              正则匹配{{ ocrPipelineSteps.regex.note }}
            </span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step" :class="ocrPipelineSteps.ai.status">
              <span class="step-dot"></span>
              AI增强{{ ocrPipelineSteps.ai.note }}
            </span>
          </div>

          <el-button
            text
            size="small"
            type="info"
            class="ocr-raw-btn"
            @click="showOcrRawDialog = true"
          >
            <el-icon style="margin-right:2px"><View /></el-icon>查看识别原文及详细诊断
          </el-button>
        </div>

        <!-- OCR 原文弹窗 -->
        <el-dialog v-model="showOcrRawDialog" title="OCR 识别详情" width="780px" top="5vh">
          <!-- AI 提取结果 -->
          <div v-if="ocrAiResult" class="ocr-ai-result">
            <h4 style="margin:0 0 8px;color:#409eff">🤖 AI 提取结果（{{ aiProviderName || 'AI' }}）</h4>
            <el-table :data="ocrAiResultRows" size="small" border>
              <el-table-column prop="field" label="字段" width="120" />
              <el-table-column prop="value" label="提取值" />
              <el-table-column prop="used" label="是否采用" width="90" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.used ? 'success' : 'info'" size="small">{{ row.used ? '已采用' : '未采用' }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
            <div style="margin-top:6px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
              <div v-if="ocrAiResult.ai_confidence" style="font-size:12px;color:#909399">
                AI 置信度：<el-tag size="small" :type="ocrAiResult.ai_confidence==='high'?'success':ocrAiResult.ai_confidence==='medium'?'warning':'danger'">{{ ocrAiResult.ai_confidence }}</el-tag>
              </div>
              <div v-if="ocrAiResult._tokens" style="font-size:12px;color:#c0c4cc">
                本次消耗 Token：{{ ocrAiResult._tokens.total.toLocaleString() }}
                <span style="margin-left:4px">（输入 {{ ocrAiResult._tokens.prompt.toLocaleString() }} + 输出 {{ ocrAiResult._tokens.completion.toLocaleString() }}）</span>
                <span style="margin-left:4px">耗时 {{ ocrAiResult._tokens.elapsed_s }}s</span>
              </div>
            </div>
            <el-divider />
          </div>
          <div v-else-if="ocrAiEnhanced === false && ocrDone" class="ocr-ai-skip">
            <el-alert type="info" :closable="false" style="margin-bottom:12px">
              <template #title>
                <span v-if="!aiConfigEnabled">AI 未启用（可在"AI 配置"中开启）</span>
                <span v-else>AI 已启用，正则识别字段完整，跳过了 AI 增强</span>
              </template>
            </el-alert>
          </div>

          <!-- v3.2: 管道诊断 -->
          <div v-if="ocrDiagnostics" class="ocr-diagnostics">
            <h4 style="margin:0 0 8px">🔍 OCR 提取管道诊断</h4>
            <el-table :data="ocrDiagnostics.layers" size="small" border stripe>
              <el-table-column prop="name" label="提取层" width="180" />
              <el-table-column prop="chars" label="字符数" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.chars > 0 ? 'success' : 'info'" size="small">{{ row.chars }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="has_chinese" label="含中文" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.has_chinese ? 'success' : 'danger'" size="small">{{ row.has_chinese ? '是' : '否' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="usable" label="可用" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.usable ? 'success' : 'warning'" size="small">{{ row.usable ? '✓' : '✗' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="关键信息" min-width="200">
                <template #default="{ row }">
                  <span v-if="row.pages_rendered" class="diag-detail">渲染 {{ row.pages_rendered }} 页</span>
                  <span v-if="row.page_count" class="diag-detail">PDF共 {{ row.page_count }} 页</span>
                  <span v-if="row.sample && row.sample.startsWith('[SKIP]')" class="diag-skip">{{ row.sample }}</span>
                  <span v-if="row.sample && row.sample.startsWith('[ERROR]')" class="diag-error">{{ row.sample }}</span>
                </template>
              </el-table-column>
            </el-table>
            <div class="diag-engine-status">
              <span>PyMuPDF: <el-tag :type="ocrDiagnostics.engines.pymupdf ? 'success' : 'danger'" size="small">{{ ocrDiagnostics.engines.pymupdf ? '已安装' : '未安装' }}</el-tag></span>
              <span>Tesseract: <el-tag :type="ocrDiagnostics.engines.tesseract ? 'success' : 'danger'" size="small">{{ ocrDiagnostics.engines.tesseract ? '已安装' : '未安装' }}</el-tag></span>
              <span v-if="ocrDiagnostics.engines.tesseract_path">路径: <code>{{ ocrDiagnostics.engines.tesseract_path }}</code></span>
            </div>
            <el-divider />
          </div>
          <pre class="ocr-text-dialog">{{ ocrRawText || '(无文字内容)' }}</pre>
        </el-dialog>

        <!-- 提交按钮 -->
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">
            {{ isEdit ? '保存修改' : '提交录入' }}
          </el-button>
          <el-button @click="handleCancel">取消</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Upload, View } from '@element-plus/icons-vue'
import { getContract, createContract, updateContract, getCompanyList, ocrRecognize, uploadAttachments } from '@/api/contract'
import api from '@/api/index'

const router = useRouter()
const route = useRoute()

const isEdit = computed(() => !!route.params.id)
const contractId = computed(() => route.params.id)

const formRef = ref(null)
const ocrUploadRef = ref(null)
const uploadRef = ref(null)
const submitting = ref(false)
const loading = ref(false)

const companyList = ref([])
const fileList = ref([])
// OCR 状态
const ocrDone = ref(false)
const ocrFilledCount = ref(0)
const ocrRawText = ref('')
const ocrDiagnostics = ref(null)  // v3.2: OCR 管道诊断信息
const ocrAiEnhanced = ref(false)  // v3.3: AI 增强标识
const ocrAiResult = ref(null)     // v3.4: AI 提取原始结果
const aiConfigEnabled = ref(true) // v3.4: AI 是否启用
const aiProviderName = ref('')    // v3.5: AI 提供商名称（用于展示）
const showOcrRawDialog = ref(false)
const ocrFields = ref([
  { key: 'contract_name', label: '合同名称', filled: false },
  { key: 'company', label: '我方公司', filled: false },
  { key: 'counterparty', label: '对方公司', filled: false },
  { key: 'amount', label: '合同金额', filled: false },
  { key: 'date', label: '签订日期', filled: false },
])

// OCR 结果标题
const ocrResultTitle = computed(() => {
  const aiTag = ocrAiEnhanced.value ? '（AI 增强）' : ''
  if (ocrFilledCount.value > 0) {
    return `OCR 识别完成${aiTag}，已填入 ${ocrFilledCount.value} 个字段，请核实`
  }
  return `OCR 识别完成${aiTag}，未能匹配到关键字段`
})

// 识别流程各步骤状态
const ocrPipelineSteps = computed(() => {
  const hasText = ocrRawText.value && !ocrRawText.value.startsWith('(OCR')
  const ocrStatus = hasText ? 'step-ok' : 'step-fail'
  const ocrNote = hasText ? `（${ocrRawText.value.length}字）` : '（无文字）'

  const regexOk = ocrFilledCount.value > 0 && !ocrAiEnhanced.value
    || (ocrFilledCount.value > 0)  // 有字段填入
  const regexFilled = ocrFields.value.filter(f => f.filled).length
  const regexNote = regexFilled > 0 ? `（识别${regexFilled}字段）` : '（0字段）'
  const regexStatus = regexFilled > 0 ? 'step-ok' : 'step-warn'

  let aiStatus, aiNote
  if (ocrAiEnhanced.value) {
    aiStatus = 'step-ok'
    aiNote = '（已增强）'
  } else if (!aiConfigEnabled.value) {
    aiStatus = 'step-skip'
    aiNote = '（未启用）'
  } else {
    aiStatus = 'step-skip'
    aiNote = '（已跳过）'
  }

  return {
    ocr: { status: ocrStatus, note: ocrNote },
    regex: { status: regexStatus, note: regexNote },
    ai: { status: aiStatus, note: aiNote },
  }
})

// AI 提取结果表格行
const ocrAiResultRows = computed(() => {
  if (!ocrAiResult.value) return []
  const fieldMap = {
    contract_name: '合同名称',
    our_company: '我方公司',
    counterparty: '对方公司',
    amount: '合同金额',
    sign_date: '签署日期',
  }
  return Object.entries(fieldMap).map(([key, label]) => {
    const val = ocrAiResult.value[key]
    // 判断是否被采用（对应字段有值且表单已填入）
    const used = !!val && val !== 'null'
    return { field: label, value: val || '(未提取到)', used }
  })
})

const pendingFiles = ref([])

const form = reactive({
  contract_no: '',
  contract_name: '',
  contract_type: '',
  company_id: null,
  counterparty: '',
  submit_date: new Date().toISOString().split('T')[0],
  valid_until: '',
  department: '',
  handler: '',
  amount: '',
  paper_copies: '',
  remarks: ''
})

const rules = {
  contract_no: [{ required: true, message: '请输入合同编号', trigger: 'blur' }],
  contract_name: [{ required: true, message: '请输入合同名称', trigger: 'blur' }],
  contract_type: [{ required: true, message: '请选择合同类型', trigger: 'change' }],
  counterparty: [{ required: true, message: '请输入对方公司', trigger: 'blur' }],
  submit_date: [{ required: true, message: '请选择提交日期', trigger: 'change' }],
  department: [{ required: true, message: '请输入所属部门', trigger: 'blur' }]
}

function handleCompanyChange(companyId) {
  // 如果需要根据公司名自动识别，可以在这里处理
}

// OCR 文件变化
async function handleOcrFileChange(file) {
  // 重置状态
  ocrDone.value = false
  ocrFilledCount.value = 0
  ocrRawText.value = ''
  ocrDiagnostics.value = null
  ocrAiEnhanced.value = false
  ocrAiResult.value = null
  ocrFields.value.forEach(f => f.filled = false)

  try {
    ElMessage.info('正在识别文字，请稍候...')
    const response = await ocrRecognize(file.raw)
    const result = response.data

    // 保存原始文本（无论是否为空都赋值，方便诊断）
    ocrRawText.value = result.raw_text || '(OCR 未提取到文字，请确认 PDF 是否为扫描件且 Tesseract 已配置)'
    // v3.2: 保存管道诊断信息
    ocrDiagnostics.value = result.diagnostics || null
    // v3.3: AI 增强标识
    ocrAiEnhanced.value = result.ai_enhanced || false
    // v3.4: AI 原始提取结果
    ocrAiResult.value = result.ai_raw || null

    // 自动回填识别到的字段
    let filledCount = 0
    // ai_mode: "full"     → 全量 AI，无条件覆盖所有字段
    // ai_mode: "fallback" → 兜底 AI，只填正则没拿到的字段（已有值不覆盖）
    // ai_mode: "none" / 未定义 → 纯正则，同兜底策略
    const aiMode = result.ai_mode || 'none'
    const overwriteAll = aiMode === 'full'

    // 合同名称：全量模式始终覆盖，其他模式也覆盖（合同名正则几乎拿不准）
    if (result.contract_name) {
      form.contract_name = result.contract_name
      ocrFields.value[0].filled = true
      filledCount++
    }
    // 对方公司
    if (result.counterparty && (overwriteAll || !form.counterparty)) {
      form.counterparty = result.counterparty
      ocrFields.value[2].filled = true
      filledCount++
    }
    // 金额
    if (result.amount && (overwriteAll || !form.amount)) {
      form.amount = result.amount
      ocrFields.value[3].filled = true
      filledCount++
    }
    // 日期
    if (result.date && (overwriteAll || !form.submit_date)) {
      form.submit_date = result.date
      ocrFields.value[4].filled = true
      filledCount++
    }

    // === v3.1 新增：我方公司自动匹配 ===
    if (result.matched_company_id) {
      ocrFields.value[1].filled = true
      filledCount++
      if (!form.company_id) {
        // 未选择时直接填入
        form.company_id = result.matched_company_id
        ElMessage.success(`已匹配我方公司：${result.matched_company_name}`)
      } else if (form.company_id !== result.matched_company_id) {
        // 已选择但与 OCR 不同，提示但不覆盖
        ElMessage.info(`OCR 识别我方公司为「${result.matched_company_name}」，与当前选择不同`)
      }
      // 如果 form.company_id === result.matched_company_id，静默通过
    }

    // 对方公司候选列表（OCR 中未匹配到我方的公司名）
    if (result.counterparty_candidates && result.counterparty_candidates.length > 1) {
      ElMessage({
        message: `检测到多个对方公司候选：${result.counterparty_candidates.join('、')}`,
        type: 'info',
        duration: 5000
      })
    }

    ocrFilledCount.value = filledCount
    ocrDone.value = true

    if (filledCount > 0) {
      const modeNote = aiMode === 'full' ? '（全量 AI 识别）' : aiMode === 'fallback' ? '（正则 + AI 兜底）' : ''
      ElMessage.success(`识别完成${modeNote}，已自动填入 ${filledCount} 个字段，请核实`)
    } else {
      ElMessage.warning('未能识别到关键字段，请查看识别原文手动填写')
    }
  } catch (error) {
    console.error('OCR 识别失败:', error)
    // 根据错误类型显示不同信息
    let errMsg = 'OCR 识别失败'
    if (error.code === 'ECONNABORTED') {
      errMsg = 'OCR 处理超时，PDF 页数过多或服务器负载过高，请稍后重试'
    } else if (error.response?.data?.raw_text) {
      // 后端返回了带 raw_text 的错误（如处理异常）
      ocrRawText.value = error.response.data.raw_text
      ocrDiagnostics.value = error.response.data.diagnostics || null
      errMsg = error.response.data.raw_text
    } else if (error.response?.data?.detail) {
      errMsg = error.response.data.detail
    } else if (error.message) {
      errMsg = `网络错误：${error.message}`
    }
    ocrRawText.value = ocrRawText.value || `(OCR 调用失败：${errMsg})`
    ElMessage.error(errMsg)
    ocrDone.value = true
  }
}

// 文件变化
function handleFileChange(file, files) {
  pendingFiles.value = files.map(f => f.raw)
}

// 文件删除
function handleFileRemove(file, files) {
  pendingFiles.value = files.map(f => f.raw)
}

// 提交
async function handleSubmit() {
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      // 清理空字符串字段：valid_until 选填，不填时传 null（Pydantic 不接受空字符串）
      const submitData = { ...form }
      if (!submitData.valid_until) submitData.valid_until = null

      let result
      if (isEdit.value) {
        result = await updateContract(contractId.value, submitData)
      } else {
        result = await createContract(submitData)
      }

      const savedId = result.data.id

      // 上传附件
      if (pendingFiles.value.length > 0) {
        await uploadAttachments(savedId, pendingFiles.value)
      }

      ElMessage.success(isEdit.value ? '修改成功' : '录入成功')
      router.push(`/contracts/${savedId}`)
    } catch (error) {
      // 错误已在拦截器处理
    } finally {
      submitting.value = false
    }
  })
}

// 取消
function handleCancel() {
  router.back()
}

// 加载编辑数据
async function loadEditData() {
  if (!isEdit.value) return

  loading.value = true
  try {
    const response = await getContract(contractId.value)
    const data = response.data
    Object.keys(form).forEach(key => {
      if (data[key] !== undefined) {
        form[key] = data[key]
      }
    })
  } catch (error) {
    ElMessage.error('加载合同信息失败')
    router.back()
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

// 加载 AI 配置（用于显示提供商名称和启用状态）
async function loadAiConfig() {
  try {
    const res = await api.get('/admin/ai-config', { silent: true })
    const data = res.data
    aiConfigEnabled.value = !!data.enabled
    // 提供商显示名
    if (data.enabled) {
      const presets = data.providers || {}
      const providerKey = data.provider || ''
      aiProviderName.value = presets[providerKey]?.name || providerKey || 'AI'
    }
  } catch (e) {
    // 非管理员无权限时静默处理，aiConfigEnabled 维持 true 不影响识别
  }
}

onMounted(() => {
  loadCompanies()
  loadAiConfig()
  if (isEdit.value) {
    loadEditData()
  }
})
</script>

<style scoped>
.contract-form-inner {
  max-width: 800px;
}

.ocr-section {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.ocr-tip {
  color: #909399;
  font-size: 13px;
}

.ocr-result-panel {
  margin-bottom: 24px;
}

.ocr-field-status {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

.ocr-field-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
  background: #f0f0f0;
  color: #909399;
}

.ocr-field-tag.filled {
  background: #e1f3d8;
  color: #67c23a;
  font-weight: 500;
}

.ocr-raw-collapse {
  margin-top: 12px;
}

.ocr-text {
  max-height: 300px;
  overflow: auto;
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  white-space: pre-wrap;
  font-size: 13px;
  margin: 0;
}

/* 查看识别原文 — 小按钮，不起眼 */
.ocr-raw-btn {
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
  padding: 0 4px;
  height: auto;
}

.ocr-raw-btn:hover {
  color: #409eff;
}

/* 弹窗中的 OCR 原文 */
.ocr-text-dialog {
  max-height: 60vh;
  overflow: auto;
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.8;
  margin: 0;
}

/* v3.2: OCR 管道诊断 */
.ocr-diagnostics {
  margin-bottom: 16px;
}

.ocr-diagnostics h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #303133;
}

.diag-detail {
  font-size: 12px;
  color: #606266;
}

.diag-skip {
  font-size: 12px;
  color: #e6a23c;
  font-style: italic;
}

.diag-error {
  font-size: 12px;
  color: #f56c6c;
  font-weight: bold;
}

.diag-engine-status {
  margin-top: 10px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.diag-engine-status code {
  font-size: 11px;
  background: #e8e8e8;
  padding: 1px 4px;
  border-radius: 2px;
}

/* v3.4: 识别流程状态栏 */
.ocr-pipeline-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 8px 0 4px;
  padding: 6px 12px;
  background: #f8f9fa;
  border-radius: 6px;
  font-size: 12px;
  flex-wrap: wrap;
}

.pipeline-label {
  color: #909399;
  font-weight: 500;
  margin-right: 4px;
}

.pipeline-arrow {
  color: #c0c4cc;
  font-size: 14px;
}

.pipeline-step {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}

.pipeline-step .step-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}

.pipeline-step.step-ok {
  background: #e1f3d8;
  color: #67c23a;
}
.pipeline-step.step-ok .step-dot { background: #67c23a; }

.pipeline-step.step-fail {
  background: #fde2e2;
  color: #f56c6c;
}
.pipeline-step.step-fail .step-dot { background: #f56c6c; }

.pipeline-step.step-warn {
  background: #fdf6ec;
  color: #e6a23c;
}
.pipeline-step.step-warn .step-dot { background: #e6a23c; }

.pipeline-step.step-skip {
  background: #f4f4f5;
  color: #909399;
}
.pipeline-step.step-skip .step-dot { background: #c0c4cc; }

/* v3.4: AI 提取结果面板 */
.ocr-ai-result {
  margin-bottom: 16px;
  padding: 12px;
  background: #ecf5ff;
  border-radius: 6px;
  border: 1px solid #b3d8ff;
}

.ocr-ai-skip {
  margin-bottom: 8px;
}
</style>
