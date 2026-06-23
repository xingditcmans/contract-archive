/**
 * Vue 应用入口文件
 * 相当于 "程序启动的第一句话"
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'

import App from './App.vue'
import router from './router'

// 创建应用实例
const app = createApp(App)

// 注册 Pinia（状态管理）
app.use(createPinia())

// 注册路由
app.use(router)

// 注册 Element Plus（UI组件库）+ 中文
app.use(ElementPlus, { locale: zhCn })

// 全局注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 挂载到页面
app.mount('#app')
