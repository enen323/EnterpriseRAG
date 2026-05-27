<template>
  <div :class="['message', message.role]">
    <div class="avatar">
      {{ message.role === 'user' ? 'U' : 'AI' }}
    </div>
    <div class="bubble">
      <div class="content">{{ message.content }}</div>
      <div v-if="message.sources && message.sources.length > 0" class="sources">
        <button class="sources-toggle" @click="showSources = !showSources">
          参考来源 ({{ message.sources.length }})
          <span :class="['arrow', { open: showSources }]">▸</span>
        </button>
        <div v-if="showSources" class="sources-list">
          <div v-for="(s, i) in message.sources" :key="i" class="source-item">
            <div class="source-header">
              <span class="source-file">{{ s.filename }}</span>
              <span class="source-score">{{ (s.score * 100).toFixed(0) }}%</span>
            </div>
            <p class="source-text">{{ s.chunk_text }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { MessageOut } from '../api'

defineProps<{ message: MessageOut }>()

const showSources = ref(false)
</script>

<style scoped>
.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 80%;
}

.message.user {
  flex-direction: row-reverse;
  margin-left: auto;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.user .avatar {
  background: #1a73e8;
  color: #fff;
}

.assistant .avatar {
  background: #34a853;
  color: #fff;
}

.bubble {
  background: #f5f5f5;
  border-radius: 12px;
  padding: 12px 16px;
  line-height: 1.6;
  font-size: 14px;
}

.user .bubble {
  background: #1a73e8;
  color: #fff;
}

.content {
  white-space: pre-wrap;
  word-break: break-word;
}

.sources {
  margin-top: 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.1);
  padding-top: 8px;
}

.user .sources {
  border-top-color: rgba(255, 255, 255, 0.2);
}

.sources-toggle {
  background: none;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  color: #666;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}

.user .sources-toggle {
  border-color: rgba(255, 255, 255, 0.3);
  color: rgba(255, 255, 255, 0.8);
}

.arrow {
  transition: transform 0.2s;
  font-size: 10px;
}

.arrow.open {
  transform: rotate(90deg);
}

.sources-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.source-item {
  background: rgba(0, 0, 0, 0.03);
  border-radius: 6px;
  padding: 8px 10px;
}

.user .source-item {
  background: rgba(255, 255, 255, 0.1);
}

.source-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.source-file {
  font-weight: 600;
  font-size: 12px;
  color: #333;
}

.user .source-file {
  color: rgba(255, 255, 255, 0.9);
}

.source-score {
  font-size: 12px;
  color: #34a853;
  font-weight: 500;
}

.source-text {
  font-size: 12px;
  color: #666;
  margin: 0;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.user .source-text {
  color: rgba(255, 255, 255, 0.7);
}
</style>
