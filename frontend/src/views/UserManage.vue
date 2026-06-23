<template>
  <div class="user-manage">
    <div class="card-container">
      <div class="page-header">
        <h2 class="page-title">用户管理</h2>
        <el-button type="primary" @click="showAddDialog = true">
          <el-icon><Plus /></el-icon>
          添加用户
        </el-button>
      </div>

      <el-table v-loading="loading" :data="userList" border stripe>
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'success'" size="small">
              {{ row.role === 'admin' ? '管理员' : '用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '正常' : '已冻结' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300">
          <template #default="{ row }">
            <el-button
              :type="row.is_active ? 'warning' : 'success'"
              link
              size="small"
              @click="handleToggleActive(row)"
            >
              {{ row.is_active ? '冻结' : '解冻' }}
            </el-button>
            <el-button
              type="primary"
              link
              size="small"
              @click="handleResetPassword(row)"
            >
              重置密码
            </el-button>
            <el-popconfirm
              title="确定要删除该用户吗？用户创建的合同不会丢失。"
              confirm-button-text="确定删除"
              cancel-button-text="取消"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button type="danger" link size="small" :disabled="row.username === 'admin'">
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 添加用户对话框 -->
    <el-dialog v-model="showAddDialog" title="添加用户" width="450px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="登录用户名，字母/数字/下划线" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="至少8位，含大小写字母+数字+符号" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="password-hint">
        <p>密码要求：</p>
        <ul>
          <li :class="passChecks.length ? 'pass' : ''">至少 8 位</li>
          <li :class="passChecks.upper ? 'pass' : ''">包含大写字母</li>
          <li :class="passChecks.lower ? 'pass' : ''">包含小写字母</li>
          <li :class="passChecks.digit ? 'pass' : ''">包含数字</li>
          <li :class="passChecks.special ? 'pass' : ''">包含特殊符号（!@#$%^&*等）</li>
        </ul>
      </div>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import api from '@/api'

const loading = ref(false)
const submitting = ref(false)
const userList = ref([])
const showAddDialog = ref(false)
const formRef = ref(null)

const form = reactive({
  username: '',
  password: '',
  role: 'user'
})

// 密码复杂度实时检测
const passChecks = computed(() => {
  const p = form.password
  return {
    length: p.length >= 8,
    upper: /[A-Z]/.test(p),
    lower: /[a-z]/.test(p),
    digit: /\d/.test(p),
    special: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(p)
  }
})

// 前端密码规则（与后端保持一致）
const validatePassword = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请输入密码'))
    return
  }
  if (value.length < 8) {
    callback(new Error('密码长度不能少于8位'))
    return
  }
  if (!/[A-Z]/.test(value)) {
    callback(new Error('密码必须包含至少一个大写字母'))
    return
  }
  if (!/[a-z]/.test(value)) {
    callback(new Error('密码必须包含至少一个小写字母'))
    return
  }
  if (!/\d/.test(value)) {
    callback(new Error('密码必须包含至少一个数字'))
    return
  }
  if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(value)) {
    callback(new Error('密码必须包含至少一个特殊符号（如 !@#$%^&*）'))
    return
  }
  callback()
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度 3-50 个字符', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { validator: validatePassword, trigger: 'blur' }
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }]
}

async function loadData() {
  loading.value = true
  try {
    const response = await api.get('/auth/users')
    userList.value = response.data
  } catch (error) {
    // 错误已在拦截器处理
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      await api.post('/auth/register', form)
      ElMessage.success('添加成功')
      showAddDialog.value = false
      loadData()
      resetForm()
    } catch (error) {
      // 错误已在拦截器处理
    } finally {
      submitting.value = false
    }
  })
}

// 冻结/解冻用户
async function handleToggleActive(row) {
  const action = row.is_active ? '冻结' : '解冻'
  try {
    const response = await api.put(`/auth/users/${row.id}/toggle-active`)
    ElMessage.success(response.data.message)
    loadData()
  } catch (error) {
    // 错误已在拦截器处理
  }
}

// 删除用户
async function handleDelete(row) {
  try {
    const response = await api.delete(`/auth/users/${row.id}`)
    const preserved = response.data.contracts_preserved || 0
    ElMessage.success(
      preserved > 0
        ? `用户已删除，保留了 ${preserved} 份合同数据`
        : '用户已删除'
    )
    loadData()
  } catch (error) {
    // 错误已在拦截器处理
  }
}

async function handleResetPassword(row) {
  try {
    const { value } = await ElMessageBox.prompt(
      `请输入用户"${row.username}"的新密码`,
      '重置密码',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputType: 'password',
        inputPlaceholder: '新密码（至少8位，含大小写+数字+符号）',
        inputValidator: (val) => {
          if (!val) return '密码不能为空'
          if (val.length < 8) return '密码长度不能少于8位'
          if (!/[A-Z]/.test(val)) return '必须包含大写字母'
          if (!/[a-z]/.test(val)) return '必须包含小写字母'
          if (!/\d/.test(val)) return '必须包含数字'
          if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(val)) return '必须包含特殊符号'
          return true
        }
      }
    )
    await api.put(`/auth/users/${row.id}/reset-password`, { password: value })
    ElMessage.success(`用户 ${row.username} 的密码已重置`)
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    // 错误已在拦截器处理
  }
}

function resetForm() {
  form.username = ''
  form.password = ''
  form.role = 'user'
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.password-hint {
  background: #f5f7fa;
  padding: 12px 16px;
  border-radius: 6px;
  margin-top: -8px;
  margin-bottom: 16px;
  font-size: 13px;
  color: #909399;
}

.password-hint p {
  margin: 0 0 4px 0;
  font-weight: 500;
}

.password-hint ul {
  margin: 0;
  padding-left: 18px;
  list-style: none;
}

.password-hint li {
  position: relative;
  padding-left: 18px;
  line-height: 1.8;
}

.password-hint li::before {
  content: '✗';
  position: absolute;
  left: 0;
  color: #909399;
}

.password-hint li.pass {
  color: #67c23a;
}

.password-hint li.pass::before {
  content: '✓';
  color: #67c23a;
}
</style>
