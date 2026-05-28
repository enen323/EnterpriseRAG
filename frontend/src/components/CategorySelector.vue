<template>
  <div class="category-selector">
    <select v-model="selected" @change="$emit('change', selected || null)">
      <option value="">All categories</option>
      <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
    </select>
    <div class="cat-actions">
      <input v-model="newName" placeholder="New category" class="cat-input" />
      <button class="btn-sm" @click="addCategory">+</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { categoryApi, type CategoryOut } from '../api'

const emit = defineEmits<{ change: [catId: string | null] }>()
const selected = ref('')
const categories = ref<CategoryOut[]>([])
const newName = ref('')

async function load() {
  try { categories.value = await categoryApi.list() } catch {}
}
async function addCategory() {
  if (!newName.value.trim()) return
  try {
    await categoryApi.create(newName.value.trim())
    newName.value = ''
    await load()
  } catch (e: any) {
    alert(e.message || 'Failed')
  }
}

onMounted(load)
</script>

<style scoped>
.category-selector { margin-bottom: 12px; }
.category-selector select { width: 100%; padding: 6px; font-size: 12px; border: 1px solid #d9d9d9; border-radius: 4px; }
.cat-actions { display: flex; gap: 4px; margin-top: 6px; }
.cat-input { flex: 1; padding: 4px 6px; font-size: 12px; border: 1px solid #d9d9d9; border-radius: 4px; }
.btn-sm { padding: 4px 8px; background: #1a73e8; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
</style>
