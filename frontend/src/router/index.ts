import { createRouter, createWebHistory } from 'vue-router'

import Diagnose from '../views/Diagnose.vue'
import Home from '../views/Home.vue'
import QuestionBank from '../views/QuestionBank.vue'
import StudentProfile from '../views/StudentProfile.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/diagnose' },
    { path: '/home', component: Home },
    { path: '/diagnose', component: Diagnose },
    { path: '/questions', component: QuestionBank },
    { path: '/profile', component: StudentProfile },
  ],
})

export default router
