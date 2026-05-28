<template>
  <div class="admin-layout">
    <aside class="admin-sidebar">
      <h2 class="admin-logo">Admin</h2>
      <nav class="admin-nav">
        <button :class="{ active: tab === 'users' }" @click="tab = 'users'; loadUsers()">Users</button>
        <button :class="{ active: tab === 'docs' }" @click="tab = 'docs'; loadDocs()">Documents</button>
        <button :class="{ active: tab === 'stats' }" @click="tab = 'stats'; loadStats()">Stats</button>
      </nav>
      <button class="back-btn" @click="$router.push('/chat')">← Back</button>
    </aside>
    <main class="admin-main">
      <div v-if="tab === 'users'">
        <h3>Users</h3>
        <table class="admin-table">
          <thead><tr><th>Username</th><th>Role</th><th>Docs</th><th>Convs</th><th>Created</th><th>Action</th></tr></thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td>{{ u.username }}</td><td>{{ u.role }}</td><td>{{ u.doc_count }}</td><td>{{ u.conv_count }}</td>
              <td>{{ new Date(u.created_at).toLocaleDateString() }}</td>
              <td><button class="btn-danger" @click="deleteUser(u.id)" :disabled="deleting">Delete</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="tab === 'docs'">
        <h3>Documents</h3>
        <table class="admin-table">
          <thead><tr><th>Filename</th><th>User</th><th>Type</th><th>Status</th><th>Chunks</th><th>Created</th></tr></thead>
          <tbody>
            <tr v-for="d in docs" :key="d.id">
              <td>{{ d.filename }}</td><td>{{ d.username }}</td><td>{{ d.file_type }}</td>
              <td>{{ d.status }}</td><td>{{ d.chunk_count }}</td>
              <td>{{ new Date(d.created_at).toLocaleDateString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="tab === 'stats'">
        <h3>Statistics</h3>
        <div class="stats-grid">
          <div class="stat-card"><span class="stat-value">{{ stats.user_count }}</span><span class="stat-label">Users</span></div>
          <div class="stat-card"><span class="stat-value">{{ stats.doc_count }}</span><span class="stat-label">Documents</span></div>
          <div class="stat-card"><span class="stat-value">{{ stats.message_count }}</span><span class="stat-label">Messages</span></div>
          <div class="stat-card"><span class="stat-value">{{ stats.new_users_7d }}</span><span class="stat-label">New Users (7d)</span></div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi } from '../api'

const tab = ref('users')
const users = ref<any[]>([])
const docs = ref<any[]>([])
const stats = ref({ user_count: 0, doc_count: 0, message_count: 0, new_users_7d: 0 })
const deleting = ref(false)

async function loadUsers() {
  try { users.value = await adminApi.users() } catch {}
}
async function loadDocs() {
  try { docs.value = await adminApi.documents() } catch {}
}
async function loadStats() {
  try { stats.value = await adminApi.stats() } catch {}
}
async function deleteUser(id: string) {
  if (!confirm('Delete this user and all their data?')) return
  deleting.value = true
  try {
    await adminApi.deleteUser(id)
    await loadUsers()
  } catch (e: any) {
    alert(e.message || 'Delete failed')
  } finally {
    deleting.value = false
  }
}

onMounted(loadUsers)
</script>

<style scoped>
.admin-layout { display: flex; height: 100vh; }
.admin-sidebar { width: 200px; background: #1a1a2e; color: #fff; display: flex; flex-direction: column; padding: 20px 0; }
.admin-logo { font-size: 18px; padding: 0 20px 20px; margin: 0; border-bottom: 1px solid rgba(255,255,255,0.1); }
.admin-nav { flex: 1; padding: 12px 0; }
.admin-nav button { display: block; width: 100%; padding: 10px 20px; background: none; border: none; color: rgba(255,255,255,0.7); text-align: left; cursor: pointer; font-size: 14px; }
.admin-nav button.active, .admin-nav button:hover { background: rgba(255,255,255,0.1); color: #fff; }
.back-btn { margin: 0 20px; padding: 8px; background: rgba(255,255,255,0.1); border: none; color: #fff; border-radius: 4px; cursor: pointer; }
.admin-main { flex: 1; padding: 24px; overflow-y: auto; }
.admin-main h3 { margin: 0 0 16px; color: #333; }
.admin-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.admin-table th, .admin-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; }
.admin-table th { background: #fafafa; font-weight: 600; color: #555; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat-card { background: #fafafa; border: 1px solid #eee; border-radius: 8px; padding: 24px; text-align: center; }
.stat-value { display: block; font-size: 32px; font-weight: 700; color: #1a73e8; }
.stat-label { display: block; font-size: 13px; color: #666; margin-top: 4px; }
.btn-danger { background: #e53935; color: #fff; border: none; border-radius: 4px; padding: 4px 10px; font-size: 12px; cursor: pointer; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
