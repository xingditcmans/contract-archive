<template>
  <div class="company-manage">
    <div class="card-container">
      <div class="page-header">
        <h2 class="page-title">我方公司管理</h2>
        <el-button type="primary" @click="showAddDialog = true">
          <el-icon><Plus /></el-icon>
          添加公司
        </el-button>
      </div>

      <el-table v-loading="loading" :data="companyList" border stripe>
        <el-table-column prop="name" label="公司名称" />
        <el-table-column prop="keywords" label="识别关键词" width="300">
          <template #default="{ row }">
            {{ row.keywords || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button type="danger" link @click="handleDelete(row)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 添加/编辑对话框 -->
    <el-dialog
      v-model="showAddDialog"
      :title="editingId ? '编辑公司' : '添加公司'"
      width="500px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="公司名称" prop="name">
          <el-input v-model="form.name" placeholder="如：济南XXX有限公司" />
        </el-form-item>
        <el-form-item label="识别关键词" prop="keywords">
          <el-input
            v-model="form.keywords"
            type="textarea"
            :rows="2"
            placeholder="用于OCR识别时自动匹配，如：济南，齐鲁"
          />
        </el-form-item>
      </el-form>

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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import {
  getCompanyList, createCompany, updateCompany, deleteCompany
} from '@/api/contract'

const loading = ref(false)
const submitting = ref(false)
const companyList = ref([])
const showAddDialog = ref(false)
const editingId = ref(null)
const formRef = ref(null)

const form = reactive({
  name: '',
  keywords: ''
})

const rules = {
  name: [{ required: true, message: '请输入公司名称', trigger: 'blur' }]
}

async function loadData() {
  loading.value = true
  try {
    const response = await getCompanyList()
    companyList.value = response.data
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function handleEdit(row) {
  editingId.value = row.id
  form.name = row.name
  form.keywords = row.keywords || ''
  showAddDialog.value = true
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定要删除"${row.name}"吗？`, '提示', { type: 'warning' })
    await deleteCompany(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      // 错误已在拦截器处理
    }
  }
}

async function handleSubmit() {
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (editingId.value) {
        await updateCompany(editingId.value, form)
      } else {
        await createCompany(form)
      }
      ElMessage.success(editingId.value ? '修改成功' : '添加成功')
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

function resetForm() {
  editingId.value = null
  form.name = ''
  form.keywords = ''
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
</style>
