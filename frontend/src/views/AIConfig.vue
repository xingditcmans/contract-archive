<template>
  <div class="ai-config-page">
    <div class="page-title">AI 识别配置</div>

    <!-- 状态提示 -->
    <el-alert
      v-if="!aiAvailable"
      title="httpx 未安装，AI 功能不可用"
      description="请在后端虚拟环境中执行: pip install httpx"
      type="warning"
      show-icon
      :closable="false"
      style="margin-bottom: 20px"
    />

    <!-- 启用开关 -->
    <el-card class="config-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>基本设置</span>
          <el-switch
            v-model="form.enabled"
            active-text="启用"
            inactive-text="禁用"
            @change="onToggleEnabled"
          />
        </div>
      </template>

      <el-form :model="form" label-width="120px" :disabled="!form.enabled">
        <!-- 提供商选择 -->
        <el-form-item label="AI 提供商">
          <el-select v-model="form.provider" placeholder="选择 AI 提供商" @change="onProviderChange" style="width: 300px">
            <el-option
              v-for="(preset, key) in providers"
              :key="key"
              :label="preset.name"
              :value="key"
            >
              <span>{{ preset.name }}</span>
              <span style="float: right; color: #8492a6; font-size: 12px">{{ preset.pricing_note }}</span>
            </el-option>
          </el-select>
        </el-form-item>

        <!-- API 地址 -->
        <el-form-item label="API 地址">
          <el-input v-model="form.api_url" placeholder="https://api.deepseek.com/v1" />
        </el-form-item>

        <!-- API Key -->
        <el-form-item label="API Key">
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            placeholder="sk-..."
          />
          <div class="form-tip">密钥仅保存在服务器本地，不会上传到任何第三方</div>
        </el-form-item>

        <!-- 模型名称 -->
        <el-form-item label="模型">
          <el-select
            v-if="currentPreset && currentPreset.models.length > 0"
            v-model="form.model"
            placeholder="选择模型"
            style="width: 300px"
            filterable
            allow-create
          >
            <el-option
              v-for="m in currentPreset.models"
              :key="m"
              :label="m"
              :value="m"
            />
          </el-select>
          <el-input
            v-else
            v-model="form.model"
            placeholder="输入模型名称，如 deepseek-chat"
            style="width: 300px"
          />
        </el-form-item>

        <!-- 高级设置 -->
        <el-divider content-position="left">高级设置</el-divider>

        <el-form-item label="调用策略">
          <el-radio-group v-model="form.fallback_only">
            <el-radio :value="true">仅兜底模式（正则识别不全时才调 AI，省钱）</el-radio>
            <el-radio :value="false">每次都调用 AI（费钱但最准）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="Max Tokens">
              <el-input-number v-model="form.max_tokens" :min="256" :max="4096" :step="256" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="Temperature">
              <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" :precision="1" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="超时(秒)">
              <el-input-number v-model="form.timeout_seconds" :min="10" :max="300" :step="10" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 操作按钮 -->
    <div style="margin-top: 20px; display: flex; gap: 12px">
      <el-button type="primary" @click="saveConfig" :loading="saving">
        <el-icon><Check /></el-icon> 保存配置
      </el-button>
      <el-button @click="testConnection" :loading="testing" :disabled="!form.enabled || !form.api_url || !form.model">
        <el-icon><Connection /></el-icon> 测试连接
      </el-button>
      <el-button @click="loadConfig" :loading="loading">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <!-- 测试结果 -->
    <el-card v-if="testResult" class="config-card" shadow="never" style="margin-top: 20px">
      <template #header>
        <span>测试结果</span>
      </template>
      <el-alert
        :title="testResult.message"
        :type="testResult.success ? 'success' : 'error'"
        :closable="false"
        show-icon
      >
        <template v-if="testResult.success" #default>
          <p>响应时间: {{ testResult.elapsed_seconds }}s</p>
          <p>Token 消耗: {{ testResult.tokens }}</p>
        </template>
        <template v-if="!testResult.success && testResult.detail" #default>
          <p style="white-space: pre-wrap; font-size: 12px; margin-top: 8px; color: #909399">{{ testResult.detail }}</p>
        </template>
      </el-alert>
    </el-card>

    <!-- 使用说明 -->
    <el-card class="config-card" shadow="never" style="margin-top: 20px">
      <template #header>
        <span>使用说明</span>
      </template>
      <div class="usage-guide">
        <h4>快速配置各平台</h4>
        <el-table :data="providerTableData" size="small" border>
          <el-table-column prop="name" label="平台" width="120" />
          <el-table-column prop="api_url" label="API 地址" />
          <el-table-column prop="model" label="推荐模型" width="160" />
          <el-table-column prop="price" label="参考价格" width="200" />
        </el-table>

        <h4 style="margin-top: 16px">工作原理</h4>
        <ol>
          <li>上传合同 PDF → OCR 提取文字（PyMuPDF / Tesseract）</li>
          <li>正则表达式快速识别关键字段</li>
          <li><strong>如果字段识别不全</ strong> → 调用 AI 模型补充识别（仅兜底模式）</li>
          <li>AI 返回结构化 JSON，自动填入表单</li>
        </ol>

        <h4 style="margin-top: 16px">费用参考</h4>
        <p>单份合同 OCR 文本约 2000-8000 字符，消耗约 500-2000 tokens。以 DeepSeek 为例：</p>
        <ul>
          <li>DeepSeek V3: 每份合同约 <strong>¥0.001~0.004</strong></li>
          <li>通义千问 Plus: 每份合同约 <strong>¥0.002~0.008</strong></li>
          <li>Ollama 本地: <strong>免费</strong>（需要本地 GPU/CPU 算力）</li>
        </ul>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, Connection, Refresh } from '@element-plus/icons-vue'
import api from '@/api/index'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref(null)
const aiAvailable = ref(true)

const providers = ref({})

const form = reactive({
  enabled: false,
  provider: '',
  api_url: '',
  api_key: '',
  model: '',
  max_tokens: 1024,
  temperature: 0.1,
  timeout_seconds: 60,
  fallback_only: true,
})

const currentPreset = computed(() => {
  if (!form.provider || !providers.value[form.provider]) return null
  return providers.value[form.provider]
})

const providerTableData = [
  { name: 'DeepSeek', api_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat', price: '¥1/百万token（极便宜）' },
  { name: '通义千问', api_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus', price: '¥0.8/百万token' },
  { name: '智谱 GLM', api_url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash', price: '免费额度充足' },
  { name: 'Ollama 本地', api_url: 'http://localhost:11434/v1', model: 'qwen3:7b', price: '免费（本地计算）' },
]

async function loadConfig() {
  loading.value = true
  testResult.value = null
  try {
    const res = await api.get('/admin/ai-config')
    const data = res.data
    aiAvailable.value = data.available !== false
    providers.value = data.providers || {}

    form.enabled = data.enabled || false
    form.provider = data.provider || ''
    form.api_url = data.api_url || ''
    form.api_key = data.api_key_masked ? '' : (data.api_key || '')  // 脱敏后不回填
    form.model = data.model || ''
    form.max_tokens = data.max_tokens || 1024
    form.temperature = data.temperature ?? 0.1
    form.timeout_seconds = data.timeout_seconds || 60
    form.fallback_only = data.fallback_only !== false
  } catch (e) {
    ElMessage.error('加载配置失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

function onProviderChange(key) {
  const preset = providers.value[key]
  if (preset) {
    if (preset.api_url) form.api_url = preset.api_url
    if (preset.default_model) form.model = preset.default_model
  }
}

function onToggleEnabled(val) {
  if (val && !form.api_url) {
    ElMessage.info('请先选择 AI 提供商')
  }
}

async function saveConfig() {
  saving.value = true
  testResult.value = null
  try {
    const payload = {
      enabled: form.enabled,
      provider: form.provider || undefined,
      api_url: form.api_url || undefined,
      model: form.model || undefined,
      max_tokens: form.max_tokens,
      temperature: form.temperature,
      timeout_seconds: form.timeout_seconds,
      fallback_only: form.fallback_only,
    }

    // 只有填了新密钥才传
    if (form.api_key && form.api_key !== '****') {
      payload.api_key = form.api_key
    }

    await api.put('/admin/ai-config', payload)
    ElMessage.success('配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    const res = await api.post('/admin/ai-test')
    testResult.value = res.data
    if (res.data.success) {
      ElMessage.success('连接测试通过！')
    } else {
      ElMessage.warning('连接测试失败，请检查配置')
    }
  } catch (e) {
    testResult.value = {
      success: false,
      message: '测试请求失败: ' + (e.response?.data?.detail || e.message),
    }
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.ai-config-page {
  max-width: 900px;
}

.config-card {
  margin-bottom: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.usage-guide h4 {
  margin-bottom: 8px;
  color: #303133;
}

.usage-guide ol,
.usage-guide ul {
  padding-left: 20px;
  line-height: 1.8;
  color: #606266;
}
</style>
