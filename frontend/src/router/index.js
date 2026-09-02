import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    redirect: '/projects',
    children: [
      {
        path: 'projects',
        name: 'Projects',
        component: () => import('@/views/Projects.vue'),
        meta: { title: '工程列表' },
      },
      {
        path: 'project/:id/dataset',
        name: 'Dataset',
        component: () => import('@/views/Dataset.vue'),
        meta: { title: '数据集管理' },
      },
      {
        path: 'project/:id/annotate',
        name: 'Annotate',
        component: () => import('@/views/Annotate.vue'),
        meta: { title: '图片标注' },
      },
      {
        path: 'project/:id/train',
        name: 'Train',
        component: () => import('@/views/Train.vue'),
        meta: { title: '模型训练' },
      },
      {
        path: 'project/:id/evaluate',
        name: 'Evaluate',
        component: () => import('@/views/Evaluate.vue'),
        meta: { title: '模型验证' },
      },
      {
        path: 'project/:id/test',
        name: 'Test',
        component: () => import('@/views/Test.vue'),
        meta: { title: '测试识别' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || 'YOLO Studio'} - YOLO Studio`
  next()
})

export default router
