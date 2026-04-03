import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import AdminView from '../views/AdminView.vue'
import GraphView from '../views/GraphView.vue'

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