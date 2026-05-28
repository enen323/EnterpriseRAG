<template>
  <div class="doc-section">
    <h3 class="section-title">文档管理</h3>

    <div class="upload-area">
      <label class="upload-btn">
        上传文档
        <input type="file" accept=".pdf,.md,.txt,.docx,.zip" multiple hidden @change="uploadFiles" />
      </label>
    </div>

    <div v-if="uploading" class="upload-progress">上传中...</div>

    <div v-if="docs.length === 0" class="empty">暂无文档</div>

    <div v-for="doc in docs" :key="doc.id" class="doc-item">
      <div class="doc-info">
        <span class="doc-name">{{ doc.filename }}</span>
        <span :class="['doc-status', doc.status]">
          {{ statusLabel(doc.status) }}
        </span>
      </div>
      <div class="doc-actions">
        <button class="btn-icon" title="预览" @click="previewDoc(doc)">&#128065;</button>
        <button class="btn-icon" title="删除" @click="removeDoc(doc.id)">
          &#10005;
        </button>
      </div>
    </div>
  </div>

  <DocPreview
    :visible="previewVisible"
    :content="previewContent"
    :filename="previewFilename"
    :file-type="previewFileType"
    @close="previewVisible = false"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { docApi, type DocumentOut } from '../api'
import DocPreview from './DocPreview.vue'

const docs = ref<DocumentOut[]>([])
const uploading = ref(false)

const previewVisible = ref(false)
const previewContent = ref('')
const previewFilename = ref('')
const previewFileType = ref('')

async function load() {
  try {
    docs.value = await docApi.list()
  } catch {}
}

async function uploadFiles(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input?.files
  if (!files || files.length === 0) return
  uploading.value = true
  let successCount = 0
  let failCount = 0
  for (const file of Array.from(files)) {
    try {
      await docApi.upload(file)
      successCount++
    } catch (err: any) {
      failCount++
      alert(`${file.name} failed: ${err.message}`)
    }
  }
  await load()
  uploading.value = false
  input.value = ''
  if (successCount > 0 && failCount > 0) {
    alert(`${successCount} uploaded, ${failCount} failed`)
  }
}

async function previewDoc(doc: DocumentOut) {
  try {
    const res = await docApi.preview(doc.id)
    previewContent.value = res.content
    previewFilename.value = res.filename
    previewFileType.value = res.file_type
    previewVisible.value = true
  } catch (err: any) {
    alert(err.message || 'Preview failed')
  }
}

async function removeDoc(id: string) {
  if (!confirm('确定删除此文档?')) return
  try {
    await docApi.delete(id)
    await load()
  } catch {}
}

function statusLabel(s: string) {
  switch (s) {
    case 'ready': return '就绪'
    case 'processing': return '处理中'
    case 'failed': return '失败'
    default: return s
  }
}

onMounted(load)
</script>

<style scoped>
.doc-section {
  padding: 0 0 16px;
  border-bottom: 1px solid #eee;
}

.section-title {
  font-size: 14px;
  color: #333;
  margin: 0 0 12px;
}

.upload-area {
  margin-bottom: 12px;
}

.upload-btn {
  display: block;
  padding: 8px 12px;
  background: #1a73e8;
  color: #fff;
  border-radius: 6px;
  text-align: center;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
}

.upload-btn:hover {
  background: #1557b0;
}

.upload-progress {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.empty {
  font-size: 12px;
  color: #999;
  text-align: center;
  padding: 12px;
}

.doc-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
}

.doc-info {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
}

.doc-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}

.doc-status {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  flex-shrink: 0;
}

.doc-status.ready {
  background: #e8f5e9;
  color: #2e7d32;
}

.doc-status.processing {
  background: #fff3e0;
  color: #e65100;
}

.doc-status.failed {
  background: #fbe9e7;
  color: #c62828;
}

.doc-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  color: #999;
  font-size: 12px;
  padding: 2px 4px;
  flex-shrink: 0;
}

.btn-icon:hover {
  color: #e53935;
}
</style>
