<template>
  <main class="page-shell">
    <!-- Welcome Banner -->
    <section class="welcome-banner surface">
      <div class="welcome-banner__content">
        <div>
          <p class="eyebrow">{{ greeting }}</p>
          <h1>{{ userName }}，准备好攻克难题了吗？</h1>
          <p class="welcome-banner__desc">
            AI 老师已为你准备好今日的学习计划，点击下方开始探索。
          </p>
        </div>
        <div class="welcome-banner__stats">
          <div class="welcome-stat">
            <strong>{{ profileData.total }}</strong>
            <span>累计错题</span>
          </div>
          <div class="welcome-stat">
            <strong>{{ profileData.mastered }}</strong>
            <span>已掌握</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Quick Entry Cards -->
    <div class="overview-grid">
      <RouterLink class="overview-tile overview-tile--diagnose" to="/diagnose">
        <div class="overview-tile__icon">
          <el-icon><Aim /></el-icon>
        </div>
        <div>
          <strong>错题诊断</strong>
          <span>上传错题，AI 精准定位错因</span>
        </div>
      </RouterLink>
      <RouterLink class="overview-tile overview-tile--questions" to="/questions">
        <div class="overview-tile__icon overview-tile__icon--orange">
          <el-icon><Notebook /></el-icon>
        </div>
        <div>
          <strong>专题题库</strong>
          <span>按知识点和难度筛选练习</span>
        </div>
      </RouterLink>
      <RouterLink class="overview-tile overview-tile--profile" to="/profile">
        <div class="overview-tile__icon overview-tile__icon--purple">
          <el-icon><TrendCharts /></el-icon>
        </div>
        <div>
          <strong>学生画像</strong>
          <span>查看薄弱点与学习路径</span>
        </div>
      </RouterLink>
    </div>

    <!-- Today's Recommendation -->
    <section class="surface today-recommend">
      <div class="section-head">
        <div>
          <p class="eyebrow">今日推荐</p>
          <h2>继续攻克</h2>
        </div>
      </div>
      <div class="recommend-hint">
        <el-icon class="recommend-hint__icon"><MagicStick /></el-icon>
        <div class="recommend-hint__text">
          <p>前往<strong>错题诊断</strong>页面，上传你的错题图片或输入题目，AI 老师将为你生成个性化的诊断讲解和相似题推荐。</p>
        </div>
        <RouterLink to="/diagnose">
          <el-button type="primary" round>
            开始诊断
            <el-icon class="el-icon--right"><ArrowRight /></el-icon>
          </el-button>
        </RouterLink>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { Aim, ArrowRight, MagicStick, Notebook, TrendCharts } from '@element-plus/icons-vue'
import { fetchProfile } from '../api/profiles'

const userName = computed(() => localStorage.getItem('edumath_user_name') || '同学')
const studentId = computed(() => localStorage.getItem('edumath_student_id') || 'S001')

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const profileData = ref({ total: 0, mastered: 0 })

onMounted(async () => {
  try {
    const res = await fetchProfile(studentId.value)
    profileData.value.total = res.data.total_wrong_questions || 0
  } catch {
    // silent
  }
})
</script>
