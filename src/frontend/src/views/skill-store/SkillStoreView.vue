<template>
  <div class="skill-repo">
    <!-- Hero 横幅 -->
    <div class="repo-hero">
      <div class="hero-inner">
        <div class="hero-text">
          <h1 class="hero-title">
            <span class="hero-icon">⚡</span>
            {{ t('views_SkillStoreView.title') }}
          </h1>
          <p class="hero-subtitle">{{ t('views_SkillStoreView.searchPlaceholder') }}</p>
        </div>
        <div class="hero-actions">
          <a-input-search
            v-model:value="searchKeyword"
            :placeholder="t('views_SkillStoreView.searchPlaceholder')"
            size="large"
            @search="handleSearch"
            class="search-input"
            allow-clear
          >
            <template #prefix><SearchOutlined /></template>
          </a-input-search>
          <a-button type="primary" size="large" class="upload-btn" @click="showUploadModal = true">
            <template #icon><UploadOutlined /></template>
            上传 Skill
          </a-button>
        </div>
      </div>
    </div>

    <!-- 主内容 -->
    <div class="repo-body">
      <div class="body-inner" :class="{ 'body-inner--empty': !loading && skills.length === 0 }">

        <!-- 加载 -->
        <div v-if="loading" class="state-box">
          <a-spin size="large" />
          <p>{{ t('views_SkillStoreView.loading') }}</p>
        </div>

        <!-- 空状态 -->
        <div v-else-if="skills.length === 0" class="state-box">
          <InboxOutlined class="state-icon" />
          <p class="state-title">{{ t('views_SkillStoreView.emptyText') }}</p>
          <p class="state-hint">{{ t('views_SkillStoreView.emptyHint') }}</p>
        </div>

        <!-- 列表 -->
        <template v-else>
          <div class="list-meta">
            <span class="meta-count">{{ t('views_SkillStoreView.resultsCount', { count: skills.length }) }}</span>
          </div>

          <div class="skills-grid">
            <div
              v-for="skill in skills"
              :key="skill.id"
              class="skill-card"
              @click="goToSkillDetail(skill.id)"
            >
              <div class="card-top">
                <div class="skill-icon-wrap">
                  <span v-if="isSvgIcon(getSkillIcon(skill.type))" v-html="getSkillIcon(skill.type)" class="skill-emoji" />
                  <span v-else class="skill-emoji">{{ getSkillIcon(skill.type) }}</span>
                </div>
                <div class="card-meta">
                  <span class="skill-type-badge">{{ skill.type }}</span>
                  <span class="skill-version">v{{ skill.version }}</span>
                </div>
              </div>

              <h3 class="skill-name">{{ skill.name }}</h3>
              <p class="skill-desc">{{ skill.description }}</p>

              <div class="card-footer">
                <span class="skill-author">
                  <UserOutlined />
                  {{ skill.author || 'Unknown' }}
                </span>
                <div class="card-footer-right">
                  <a-popconfirm
                    v-if="isAdmin"
                    title="确认删除该 Skill？此操作不可撤销"
                    ok-text="删除"
                    cancel-text="取消"
                    ok-type="danger"
                    @confirm="handleDelete(skill, $event)"
                    @click.stop
                  >
                    <button class="del-btn" title="删除" @click.stop>
                      <DeleteOutlined />
                    </button>
                  </a-popconfirm>
                  <span class="card-arrow"><RightOutlined /></span>
                </div>
              </div>
            </div>
          </div>
        </template>

      </div>
    </div>
  <!-- 上传 Skill Modal -->
  <a-modal
    v-model:open="showUploadModal"
    title="上传 Skill"
    :footer="null"
    :width="480"
    @cancel="resetUpload"
  >
    <div class="upload-modal-body">
      <!-- 拖拽区 -->
      <div
        class="drop-zone"
        :class="{ 'drop-active': isDroppingFile, 'has-file': selectedFile }"
        @dragover.prevent="isDroppingFile = true"
        @dragleave.prevent="isDroppingFile = false"
        @drop.prevent="handleFileDrop"
        @click="fileInput?.click()"
      >
        <input ref="fileInput" type="file" accept=".zip" style="display:none" @change="handleFileChange" />
        <template v-if="!selectedFile">
          <InboxOutlined class="drop-icon" />
          <p class="drop-title">点击或拖拽 zip 包到此处</p>
          <p class="drop-hint">仅支持 .zip 格式，zip 根目录需包含 SKILL.md</p>
        </template>
        <template v-else>
          <FileZipOutlined class="drop-icon file-selected" />
          <p class="drop-title">{{ selectedFile.name }}</p>
          <p class="drop-hint">{{ (selectedFile.size / 1024).toFixed(1) }} KB · 点击重新选择</p>
        </template>
      </div>

      <!-- 进度条 -->
      <a-progress
        v-if="uploading"
        :percent="uploadProgress"
        status="active"
        style="margin-top: 16px"
      />

      <!-- 操作按钮 -->
      <div class="modal-footer">
        <a-button @click="resetUpload">取消</a-button>
        <a-button
          type="primary"
          :loading="uploading"
          :disabled="!selectedFile"
          @click="doUpload"
        >
          {{ uploading ? '上传中...' : '确认上传' }}
        </a-button>
      </div>
    </div>
  </a-modal>
</div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { SearchOutlined, InboxOutlined, UserOutlined, RightOutlined, UploadOutlined, FileZipOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { getSkills, uploadSkill, deleteSkill, type SkillInfo } from '@/apis/skills'
import { useAuthStore } from '@/store/auth'
import { getSkillIcon, isSvgIcon } from '@/utils/skillIcon'

const router = useRouter()
const { t } = useI18n()
const authStore = useAuthStore()
const isAdmin = computed(() => authStore.user?.role === 'admin')

const loading = ref(true)
const skills = ref<SkillInfo[]>([])
const searchKeyword = ref('')

// 上传相关
const showUploadModal = ref(false)
const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const uploadProgress = ref(0)
const isDroppingFile = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

onMounted(async () => {
  await loadSkills()
})

const loadSkills = async () => {
  loading.value = true
  try {
    const data = await getSkills(undefined, searchKeyword.value || undefined)
    skills.value = data
  } catch (error) {
    console.error(t('views_SkillStoreView.loadSkillsFailed'), error)
    message.error(t('views_SkillStoreView.loadSkillsFailed'))
  } finally {
    loading.value = false
  }
}

const handleSearch = () => loadSkills()

const goToSkillDetail = (id: string) => {
  router.push(`/skill-store/${id}`)
}

const handleDelete = async (skill: SkillInfo, e: Event) => {
  e.stopPropagation()
  try {
    await deleteSkill(skill.id)
    message.success(`已删除 ${skill.name}`)
    await loadSkills()
  } catch {
    message.error('删除失败')
  }
}

const handleFileChange = (e: Event) => {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) selectedFile.value = f
}

const handleFileDrop = (e: DragEvent) => {
  isDroppingFile.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f && f.name.endsWith('.zip')) {
    selectedFile.value = f
  } else {
    message.warning('请上传 .zip 格式文件')
  }
}

const doUpload = async () => {
  if (!selectedFile.value) return
  uploading.value = true
  uploadProgress.value = 0
  try {
    await uploadSkill(selectedFile.value, (p) => { uploadProgress.value = p })
    message.success('Skill 上传成功')
    showUploadModal.value = false
    resetUpload()
    await loadSkills()
  } catch (e) {
    message.error('上传失败，请检查 zip 包格式')
  } finally {
    uploading.value = false
  }
}

const resetUpload = () => {
  selectedFile.value = null
  uploadProgress.value = 0
  uploading.value = false
  if (fileInput.value) fileInput.value.value = ''
}
</script>

<style scoped>
/* ── Hero actions ── */
.hero-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 0 0 500px;
}

.hero-actions .search-input {
  flex: 1;
}

.upload-btn {
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── 上传 Modal ── */
.upload-modal-body {
  padding: 8px 0 4px;
}

.drop-zone {
  border: 2px dashed var(--border-color);
  border-radius: 12px;
  padding: 36px 20px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  background: var(--bg-secondary);
}

.drop-zone:hover,
.drop-zone.drop-active {
  border-color: var(--link-color);
  background: color-mix(in srgb, var(--link-color) 5%, var(--bg-secondary));
}

.drop-zone.has-file {
  border-color: #52c41a;
  background: color-mix(in srgb, #52c41a 5%, var(--bg-secondary));
}

.drop-icon {
  font-size: 40px;
  color: var(--text-tertiary);
  margin-bottom: 12px;
  display: block;
}

.drop-icon.file-selected { color: #52c41a; }

.drop-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0 0 6px;
}

.drop-hint {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 0;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
/* ── 整体容器 ── */
.skill-repo {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
}

/* ── Hero 横幅 ── */
.repo-hero {
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #1a56a0 100%);
  padding: 48px 32px 40px;
}

.hero-inner {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 40px;
  flex-wrap: wrap;
}

.hero-text { flex: 1; min-width: 0; }

.hero-title {
  font-size: 32px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 8px 0;
  display: flex;
  align-items: center;
  gap: 12px;
  letter-spacing: -0.3px;
}

.hero-icon { font-size: 28px; }

.hero-subtitle {
  font-size: 15px;
  color: rgba(255,255,255,0.65);
  margin: 0;
}


.search-input :deep(.ant-input-group-wrapper) {
  border-radius: 10px;
}
.search-input :deep(.ant-input-affix-wrapper) {
  border-radius: 10px 0 0 10px;
}
.search-input :deep(.ant-input-search-button) {
  border-radius: 0 10px 10px 0;
  margin-left: 8px;
  min-width: 72px;
}

/* ── 主体 ── */
.repo-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.body-inner {
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 32px 32px 48px;
  flex: 1;
}

.body-inner--empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

/* ── 状态框 ── */
.state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
  gap: 12px;
}

.state-icon { font-size: 64px; color: var(--border-color); }
.state-title { font-size: 18px; color: var(--text-secondary); margin: 0; }
.state-hint  { font-size: 14px; color: var(--text-tertiary); margin: 0; }

/* ── 列表元信息 ── */
.list-meta {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.meta-count {
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  padding: 3px 12px;
}

/* ── 网格 ── */
.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

/* ── 卡片 ── */
.skill-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px 22px 16px;
  cursor: pointer;
  transition: box-shadow 0.18s, border-color 0.18s, transform 0.15s;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skill-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.10);
  border-color: var(--link-color);
  transform: translateY(-2px);
}

/* 卡片顶部：图标 + 徽标 */
.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.skill-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--link-color) 10%, var(--bg-secondary));
  display: flex;
  align-items: center;
  justify-content: center;
}

.skill-emoji { font-size: 26px; line-height: 1; }

.card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}

.skill-type-badge {
  font-size: 11px;
  font-weight: 600;
  color: var(--link-color);
  background: color-mix(in srgb, var(--link-color) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--link-color) 25%, transparent);
  padding: 2px 8px;
  border-radius: 20px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.skill-version {
  font-size: 11px;
  color: var(--text-tertiary);
}

/* 卡片文字 */
.skill-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.skill-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
  flex: 1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 卡片底部 */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
  padding-top: 10px;
  border-top: 1px solid var(--bg-secondary);
}

.skill-author {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.card-footer-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.del-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  cursor: pointer;
  border-radius: 4px;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s, background 0.15s;
}

.skill-card:hover .del-btn { opacity: 1; }
.del-btn:hover {
  color: #ff4d4f;
  background: rgba(255, 77, 79, 0.08);
}

.card-arrow {
  font-size: 12px;
  color: var(--border-color);
  transition: color 0.15s;
}
.skill-card:hover .card-arrow { color: var(--link-color); }

/* ── 响应式 ── */
@media (max-width: 768px) {
  .repo-hero { padding: 32px 20px 28px; }
  .hero-inner { flex-direction: column; gap: 20px; }
  .hero-actions { flex: 1; width: 100%; flex-wrap: wrap; }
  .body-inner { padding: 24px 16px; }
  .skills-grid { grid-template-columns: 1fr; }
}
</style>
