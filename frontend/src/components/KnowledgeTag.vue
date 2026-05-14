<template>
  <el-tag class="knowledge-tag" effect="plain" round>{{ label }}</el-tag>
</template>

<script setup lang="ts">
defineProps<{ label: string }>()
</script>
