import { createRouter, createWebHistory } from 'vue-router'

import Diagnose from '../views/Diagnose.vue'
import Home from '../views/Home.vue'
import Login from '../views/Login.vue'
import QuestionBank from '../views/QuestionBank.vue'
import StudentProfile from '../views/StudentProfile.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/', redirect: '/home' },
    { path: '/home', component: Home },
    { path: '/diagnose', component: Diagnose },
    { path: '/questions', component: QuestionBank },
    { path: '/profile', component: StudentProfile },
  ],
})

router.beforeEach((to) => {
  const studentId = localStorage.getItem('edumath_student_id')
  if (!studentId && to.path !== '/login') {
    return '/login'
  }
  if (studentId && to.path === '/login') {
    return '/home'
  }
})

export default router
