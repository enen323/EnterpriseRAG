<template>
  <div v-if="visible" class="preview-overlay" @click.self="$emit('close')">
    <div class="preview-modal">
      <div class="preview-header">
        <span class="preview-title">{{ filename }}</span>
        <button class="preview-close" @click="$emit('close')">&#10005;</button>
      </div>
      <div class="preview-body">
        <pre v-if="fileType === '.txt'" class="preview-text">{{ content }}</pre>
        <div v-else-if="fileType === '.md'" class="preview-markdown">{{ content }}</div>
        <div v-else class="preview-text">{{ content }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  content: string
  filename: string
  fileType: string
}>()
defineEmits<{ close: [] }>()
</script>

<style scoped>
.preview-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.preview-modal {
  background: #fff; border-radius: 12px; width: 80%; max-width: 800px;
  max-height: 80vh; display: flex; flex-direction: column; box-shadow: 0 4px 24px rgba(0,0,0,0.15);
}
.preview-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #eee;
}
.preview-title { font-weight: 600; font-size: 15px; }
.preview-close { background: none; border: none; font-size: 18px; cursor: pointer; color: #999; }
.preview-close:hover { color: #333; }
.preview-body {
  padding: 20px; overflow-y: auto; flex: 1;
}
.preview-text { white-space: pre-wrap; font-size: 13px; line-height: 1.6; }
.preview-markdown { font-size: 14px; line-height: 1.6; }
</style>
