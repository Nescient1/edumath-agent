<template>
  <div class="login-page">
    <!-- Decorative Background -->
    <div class="login-bg">
      <div class="login-bg__shapes">
        <div class="shape shape--1"></div>
        <div class="shape shape--2"></div>
        <div class="shape shape--3"></div>
        <div class="shape shape--4"></div>
      </div>
      <div class="login-bg__content">
        <div class="login-bg__brand">
          <span class="login-brand-mark">E</span>
          <span class="login-brand-text">EduMath Agent</span>
        </div>
        <h1 class="login-bg__title">AI 驱动的<br />数学错题诊断引擎</h1>
        <p class="login-bg__subtitle">
          精准识别错因，个性化讲解路径，<br />让每一道错题都成为提分的阶梯。
        </p>
        <div class="login-bg__features">
          <div class="feature-item">
            <div class="feature-icon">
              <el-icon><Aim /></el-icon>
            </div>
            <span>RAG 知识库检索</span>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <el-icon><DataAnalysis /></el-icon>
            </div>
            <span>学情画像分析</span>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <el-icon><MagicStick /></el-icon>
            </div>
            <span>AI 变式题生成</span>
          </div>
        </div>
      </div>
      <!-- Floating math formulas -->
      <div class="floating-formulas">
        <span class="formula formula--1">f'(x) = 3x² - 3</span>
        <span class="formula formula--2">∫ sin(x) dx</span>
        <span class="formula formula--3">lim x→∞</span>
        <span class="formula formula--4">Σ n=1→∞</span>
        <span class="formula formula--5">Δ = b²-4ac</span>
      </div>
    </div>

    <!-- Login Form -->
    <div class="login-form-area">
      <div class="login-card">
        <div class="login-card__header">
          <h2>欢迎回来</h2>
          <p>登录你的学习账号，继续攻克难题</p>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @submit.prevent="handleLogin"
        >
          <el-form-item label="学生 ID" prop="student_id">
            <el-input
              v-model="form.student_id"
              placeholder="输入你的学号，如 S001"
              size="large"
              :prefix-icon="User"
              clearable
            />
          </el-form-item>

          <el-form-item label="姓名（选填）" prop="name">
            <el-input
              v-model="form.name"
              placeholder="你的名字，方便 AI 称呼你"
              size="large"
              :prefix-icon="UserFilled"
              clearable
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              class="login-btn"
              native-type="submit"
              :loading="loading"
            >
              开始学习
              <el-icon class="el-icon--right"><ArrowRight /></el-icon>
            </el-button>
          </el-form-item>
        </el-form>

        <div class="login-card__footer">
          <p>输入学号即可快速体验，无需注册</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  Aim,
  ArrowRight,
  DataAnalysis,
  MagicStick,
  User,
  UserFilled,
} from '@element-plus/icons-vue'

const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  student_id: '',
  name: '',
})

const rules: FormRules = {
  student_id: [
    { required: true, message: '请输入学生 ID', trigger: 'blur' },
  ],
}

async function handleLogin() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    localStorage.setItem('edumath_student_id', form.student_id.trim())
    if (form.name.trim()) {
      localStorage.setItem('edumath_user_name', form.name.trim())
    } else {
      localStorage.setItem('edumath_user_name', '同学')
    }
    ElMessage.success('登录成功，欢迎回来！')
    router.push('/home')
  } finally {
    loading.value = false
  }
}
</script>
