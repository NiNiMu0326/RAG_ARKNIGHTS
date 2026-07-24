import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'

// 路由级代码分割：管理后台和知识图谱（含 cytoscape）按需加载，减小首屏体积
const AdminView = () => import('../views/AdminView.vue')
const GraphView = () => import('../views/GraphView.vue')

const routes = [
  { path: '/', redirect: '/chat' },
  { path: '/chat', name: 'chat', component: ChatView },
  { path: '/admin', name: 'admin', component: AdminView },
  { path: '/graph', name: 'graph', component: GraphView }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router