/**
 * 路由配置
 * 定义每个 URL 对应显示哪个页面
 */
import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 页面组件（懒加载，提高性能）
const Login = () => import('@/views/Login.vue')
const Dashboard = () => import('@/views/Dashboard.vue')
const ContractList = () => import('@/views/ContractList.vue')
const ContractForm = () => import('@/views/ContractForm.vue')
const ContractDetail = () => import('@/views/ContractDetail.vue')
const CompanyManage = () => import('@/views/CompanyManage.vue')
const UserManage = () => import('@/views/UserManage.vue')
const BackupRestore = () => import('@/views/BackupRestore.vue')
const AIConfig = () => import('@/views/AIConfig.vue')

// 路由规则
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: Dashboard,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/contracts'
      },
      {
        path: 'contracts',
        name: 'ContractList',
        component: ContractList,
        meta: { title: '合同列表' }
      },
      {
        path: 'contracts/create',
        name: 'ContractCreate',
        component: ContractForm,
        meta: { title: '录入合同' }
      },
      {
        path: 'contracts/:id',
        name: 'ContractDetail',
        component: ContractDetail,
        meta: { title: '合同详情' }
      },
      {
        path: 'contracts/:id/edit',
        name: 'ContractEdit',
        component: ContractForm,
        meta: { title: '编辑合同' }
      },
      {
        path: 'companies',
        name: 'CompanyManage',
        component: CompanyManage,
        meta: { title: '公司管理', requiresAdmin: true }
      },
      {
        path: 'users',
        name: 'UserManage',
        component: UserManage,
        meta: { title: '用户管理', requiresAdmin: true }
      },
      {
        path: 'backup',
        name: 'BackupRestore',
        component: BackupRestore,
        meta: { title: '备份与恢复', requiresAdmin: true }
      },
      {
        path: 'ai-config',
        name: 'AIConfig',
        component: AIConfig,
        meta: { title: 'AI 识别配置', requiresAdmin: true }
      }
    ]
  }
]

// 创建路由实例
const router = createRouter({
  // hash 模式：配合 iframe 隔离方案，杜绝窗口跳闪
  history: createWebHashHistory(),
  routes
})

// 标记：是否已经验证过 token 有效性（每次页面刷新后重置）
let tokenVerified = false

// 路由守卫：检查是否登录
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // 首次加载时，如果 localStorage 有 token，需要向后端验证是否仍然有效
  // 避免 token 过期后仍然直接进入系统
  if (!tokenVerified && authStore.token) {
    tokenVerified = true
    try {
      await authStore.fetchUserInfo()
    } catch (error) {
      // token 无效（过期/篡改），清掉并跳到登录页
      authStore.logout()
      next('/login')
      return
    }
  }

  // 如果页面需要登录
  if (to.meta.requiresAuth !== false && !authStore.isLoggedIn) {
    next('/login')
    return
  }

  // 如果页面需要管理员权限
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    ElMessage.error('需要管理员权限')
    next('/contracts')
    return
  }

  // 已登录访问登录页，跳转到首页
  if (to.path === '/login' && authStore.isLoggedIn) {
    next('/')
    return
  }

  next()
})

export default router
