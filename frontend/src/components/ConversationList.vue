<template>
  <div class="conv-section">
    <div class="conv-header">
      <h3 class="section-title">对话历史</h3>
      <button class="btn-new" @click="$emit('new')">+ 新对话</button>
    </div>

    <div v-if="convs.length === 0" class="empty">暂无对话</div>

    <div
      v-for="conv in convs"
      :key="conv.id"
      :class="['conv-item', { active: conv.id === activeId }]"
      @click="$emit('select', conv.id)"
    >
      <span class="conv-title">{{ conv.title }}</span>
      <button class="btn-icon" title="删除" @click.stop="remove(conv.id)">
        ✕
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { convApi, type ConversationOut } from '../api'

defineProps<{
  activeId?: string
}>()

const emit = defineEmits<{
  select: [id: string]
  new: []
}>()

const convs = ref<ConversationOut[]>([])

async function load() {
  try {
    convs.value = await convApi.list()
  } catch {}
}

async function remove(id: string) {
  if (!confirm('确定删除此对话?')) return
  try {
    await convApi.delete(id)
    await load()
  } catch {}
}

defineExpose({ load })

onMounted(load)
</script>

<style scoped>
.conv-section {
  padding: 16px 0 0;
  flex: 1;
  overflow-y: auto;
}

.conv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-title {
  font-size: 14px;
  color: #333;
  margin: 0;
}

.btn-new {
  background: none;
  border: 1px solid #1a73e8;
  color: #1a73e8;
  border-radius: 4px;
  padding: 3px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-new:hover {
  background: #1a73e8;
  color: #fff;
}

.empty {
  font-size: 12px;
  color: #999;
  text-align: center;
  padding: 12px;
}

.conv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
  margin-bottom: 2px;
}

.conv-item:hover {
  background: #f0f2f5;
}

.conv-item.active {
  background: #e3f2fd;
  color: #1a73e8;
  font-weight: 500;
}

.conv-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  color: #999;
  font-size: 11px;
  padding: 2px 4px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s;
}

.conv-item:hover .btn-icon {
  opacity: 1;
}

.btn-icon:hover {
  color: #e53935;
}
</style>
