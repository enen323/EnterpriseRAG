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
      <div v-if="message.role === 'assistant' && message.id && !message.id.startsWith('temp-')" class="feedback">
        <button :class="['btn-feedback', { active: feedbackValue === 'up' }]" @click="vote('up')" title="Helpful">👍</button>
        <button :class="['btn-feedback', { active: feedbackValue === 'down' }]" @click="vote('down')" title="Not helpful">👎</button>
        <div v-if="showCommentBox" class="comment-box">
          <textarea v-model="commentText" placeholder="Optional comment" rows="2"></textarea>
          <button class="btn-submit-comment" @click="submitFeedback">Submit</button>
        </div>
      </div>
      <div v-if="message.suggested_questions && message.suggested_questions.length > 0" class="suggested">
        <span class="suggested-label">Follow up:</span>
        <button v-for="(q, i) in message.suggested_questions" :key="i" class="chip" @click="$emit('suggestClick', q)">
          {{ q }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { MessageOut } from '../api'
import { qaApi } from '../api'

const props = defineProps<{ message: MessageOut }>()
const emit = defineEmits<{ suggestClick: [question: string] }>()

const showSources = ref(false)
const feedbackValue = ref<string | null>(null)
const showCommentBox = ref(false)
const commentText = ref('')

async function vote(type: string) {
  if (feedbackValue.value === type) {
    feedbackValue.value = null
  } else {
    feedbackValue.value = type
    if (type === 'down') {
      showCommentBox.value = true
    } else {
      await qaApi.feedback({ message_id: props.message.id as string, feedback: type })
    }
  }
}

async function submitFeedback() {
  await qaApi.feedback({
    message_id: props.message.id as string,
    feedback: feedbackValue.value || 'down',
    comment: commentText.value || undefined,
  })
  showCommentBox.value = false
  commentText.value = ''
}
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

.feedback {
  margin-top: 8px;
  display: flex;
  gap: 4px;
  align-items: flex-start;
}

.btn-feedback {
  background: none;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  padding: 2px 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-feedback.active {
  border-color: #1a73e8;
  background: #e8f0fe;
}

.comment-box {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.comment-box textarea {
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  padding: 4px;
  font-size: 12px;
  width: 200px;
}

.btn-submit-comment {
  background: #1a73e8;
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
  cursor: pointer;
  align-self: flex-end;
}

.suggested {
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 0, 0, 0.1);
}

.suggested-label {
  font-size: 12px;
  color: #666;
  margin-right: 6px;
}

.chip {
  display: inline-block;
  margin: 2px 4px 2px 0;
  padding: 4px 10px;
  background: #f0f0f0;
  border: 1px solid #d9d9d9;
  border-radius: 12px;
  font-size: 12px;
  cursor: pointer;
  color: #333;
  transition: all 0.2s;
}

.chip:hover {
  background: #e3f2fd;
  border-color: #1a73e8;
  color: #1a73e8;
}
</style>
