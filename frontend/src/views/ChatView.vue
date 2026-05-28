<template>
  <div class="chat-layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <h2 class="logo">EnterpriseRAG</h2>
      </div>

      <DocumentList ref="docListRef" />

      <ConversationList
        ref="convListRef"
        :activeId="conversationId"
        @select="loadConversation"
        @new="newConversation"
      />

      <div class="sidebar-footer">
        <span class="user-name">{{ auth.user?.username }}</span>
        <div class="sidebar-footer-actions">
          <router-link v-if="auth.user?.role === 'admin'" to="/admin" class="admin-link">管理</router-link>
          <button class="btn-logout" @click="handleLogout">退出</button>
        </div>
      </div>
    </aside>

    <!-- Main chat area -->
    <main class="chat-main">
      <div v-if="messages.length === 0" class="welcome">
        <h2>企业级知识库问答系统</h2>
        <p>上传文档后即可开始提问</p>
      </div>

      <div v-else ref="msgContainer" class="messages">
        <ChatMessage
          v-for="msg in messages"
          :key="msg.id"
          :message="msg"
          @suggest-click="(q: string) => { question = q; sendQuestion() }"
        />
        <div v-if="loading" class="message assistant">
          <div class="avatar">AI</div>
          <div class="bubble typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>

      <div v-if="error" class="error-bar">{{ error }}</div>

      <div class="input-area">
        <input
          v-model="question"
          type="text"
          placeholder="输入问题..."
          :disabled="loading"
          @keydown.enter.prevent="sendQuestion"
        />
        <button :disabled="loading || !question.trim()" @click="sendQuestion">
          发送
        </button>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { qaApi, convApi, type MessageOut, type SourceItem, type StreamMetadata } from '../api'
import ChatMessage from '../components/ChatMessage.vue'
import DocumentList from '../components/DocumentList.vue'
import ConversationList from '../components/ConversationList.vue'

const router = useRouter()
const auth = useAuthStore()

const messages = ref<(MessageOut)[]>([])
const question = ref('')
const loading = ref(false)
const error = ref('')
const conversationId = ref<string | undefined>(undefined)

const msgContainer = ref<HTMLElement | null>(null)
const convListRef = ref<InstanceType<typeof ConversationList> | null>(null)
const docListRef = ref<InstanceType<typeof DocumentList> | null>(null)

function newConversation() {
  messages.value = []
  conversationId.value = undefined
  error.value = ''
}

async function loadConversation(id: string) {
  if (loading.value) return
  conversationId.value = id
  error.value = ''
  try {
    const msgs = await convApi.get(id)
    messages.value = msgs
    await nextTick()
    scrollToBottom()
  } catch (e: any) {
    error.value = e.message || '加载对话失败'
  }
}

async function sendQuestion() {
  const q = question.value.trim()
  if (!q || loading.value) return

  question.value = ''
  error.value = ''
  loading.value = true

  // Optimistically add user message
  const tempUserMsg: MessageOut = {
    id: 'temp-' + Date.now(),
    role: 'user',
    content: q,
    sources: null,
    created_at: new Date().toISOString(),
  }
  messages.value.push(tempUserMsg)

  // Add temporary assistant message — content updates progressively via SSE
  const tempAssistantMsg: MessageOut = {
    id: 'temp-assistant-' + Date.now(),
    role: 'assistant',
    content: '',
    sources: null,
    created_at: new Date().toISOString(),
  }
  messages.value.push(tempAssistantMsg)
  scrollToBottom()

  let accumulated = ''

  qaApi.askStream({
    question: q,
    conversation_id: conversationId.value || null,
  }, {
    onToken(token: string) {
      accumulated += token
      const idx = messages.value.findIndex(m => m.id === tempAssistantMsg.id)
      if (idx >= 0) {
        messages.value[idx] = { ...messages.value[idx], content: accumulated }
      }
      scrollToBottom()
    },
    onDone(metadata: StreamMetadata) {
      // Replace temp messages with real persisted messages
      messages.value = messages.value.filter(
        m => m.id !== tempUserMsg.id && m.id !== tempAssistantMsg.id
      )
      messages.value.push({
        id: 'user-' + Date.now(),
        role: 'user',
        content: q,
        sources: null,
        created_at: new Date().toISOString(),
      })
      messages.value.push({
        id: 'assistant-' + Date.now(),
        role: 'assistant',
        content: accumulated,
        sources: metadata.sources as SourceItem[],
        created_at: new Date().toISOString(),
      })
      conversationId.value = metadata.conversation_id
      convListRef.value?.load()
      scrollToBottom()
      loading.value = false
    },
    onError(msg: string) {
      error.value = msg
      // Remove temp messages on error
      messages.value = messages.value.filter(
        m => m.id !== tempUserMsg.id && m.id !== tempAssistantMsg.id
      )
      loading.value = false
    },
  })
}

// Non-streaming fallback — kept for reference or when SSE is unavailable
// async function sendQuestionNonStreaming(q: string, tempUserMsg: MessageOut) { ... }

function scrollToBottom() {
  nextTick(() => {
    const container = msgContainer.value
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  })
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(() => {
  if (!auth.user) {
    auth.loadUser()
  }
})
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  background: #fff;
}

/* Sidebar */
.sidebar {
  width: 280px;
  background: #fafafa;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 16px 16px 12px;
  border-bottom: 1px solid #eee;
}

.logo {
  font-size: 18px;
  margin: 0;
  color: #1a1a2e;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid #eee;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.user-name {
  font-size: 13px;
  color: #333;
  font-weight: 500;
}

.sidebar-footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.admin-link {
  font-size: 13px;
  color: #1a73e8;
  text-decoration: none;
}

.admin-link:hover {
  text-decoration: underline;
}

.btn-logout {
  background: none;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 12px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-logout:hover {
  border-color: #e53935;
  color: #e53935;
}

/* Main */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #999;
}

.welcome h2 {
  color: #333;
  margin: 0 0 8px;
}

.welcome p {
  margin: 0;
  font-size: 14px;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

/* Typing indicator */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 14px 20px;
  align-items: center;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: #999;
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}

/* Error */
.error-bar {
  margin: 0 32px 12px;
  padding: 8px 12px;
  background: #fbe9e7;
  color: #c62828;
  border-radius: 6px;
  font-size: 13px;
}

/* Input */
.input-area {
  display: flex;
  gap: 8px;
  padding: 16px 32px 24px;
  border-top: 1px solid #eee;
}

.input-area input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.input-area input:focus {
  border-color: #1a73e8;
  box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.1);
}

.input-area button {
  padding: 10px 20px;
  background: #1a73e8;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.input-area button:hover {
  background: #1557b0;
}

.input-area button:disabled {
  background: #93b8f0;
  cursor: not-allowed;
}
</style>
