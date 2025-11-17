<template>
  <a-modal
    v-model:open="visible"
    :title="t('components_UserProfileModal.title')"
    :confirm-loading="saving"
    :width="500"
    :cancelText="t('components_UserProfileModal.cancel')"
    :okText="t('components_UserProfileModal.save')"
    @ok="handleSave"
    @cancel="handleCancel"
  >
    <div class="user-profile-form">
      <!-- 头像编辑区域 -->
      <div class="avatar-section">
        <div class="avatar-preview">
          <div v-if="!avatarUrl" class="avatar-placeholder">
            {{ displayName.charAt(0).toUpperCase() }}
          </div>
          <img v-else :src="avatarUrl" :alt="displayName" class="avatar-image" />
        </div>
        
        <div class="avatar-actions">
          <a-button @click="triggerAvatarUpload" :loading="uploadingAvatar">
            <UploadOutlined />
            {{ avatarUrl ? t('components_UserProfileModal.changeAvatar') : t('components_UserProfileModal.uploadAvatar') }}
          </a-button>
          <a-button 
            v-if="avatarUrl" 
            @click="removeAvatar" 
            type="text" 
            danger
          >
            <DeleteOutlined />
            {{ t('components_UserProfileModal.removeAvatar') }}
          </a-button>
        </div>
        
        <!-- 隐藏的文件上传input -->
        <input
          ref="avatarInputRef"
          type="file"
          accept="image/*"
          style="display: none"
          @change="handleAvatarUpload"
        />
      </div>

      <!-- 用户信息表单 -->
      <a-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        layout="vertical"
        class="profile-form"
      >
        <a-form-item :label="t('components_UserProfileModal.username')" name="user_name">
          <a-input
            v-model:value="formData.user_name"
            :placeholder="t('components_UserProfileModal.usernamePlaceholder')"
            :maxlength="20"
            show-count
          />
        </a-form-item>

        <a-form-item :label="t('components_UserProfileModal.userId')" name="uid">
          <a-input
            :value="formData.uid"
            disabled
            :placeholder="t('components_UserProfileModal.userIdNote')"
          />
        </a-form-item>

        <a-form-item :label="t('components_UserProfileModal.role')" name="role">
          <a-tag :color="roleColor">
            {{ roleText }}
          </a-tag>
        </a-form-item>
      </a-form>

      <!-- 头像上传提示 -->
      <div class="upload-tips">
        <h4>{{ t('components_UserProfileModal.uploadInstructions') }}</h4>
        <ul>
          <li>{{ t('components_UserProfileModal.supportedFormats') }}</li>
          <li>{{ t('components_UserProfileModal.maxSize') }}</li>
          <li>{{ t('components_UserProfileModal.recommendedSize') }}</li>
          <li>{{ t('components_UserProfileModal.storageFormat') }}</li>
        </ul>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { DeleteOutlined, UploadOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/store/auth'
import type { UserInfo } from '@/types/auth'
import { useI18n } from 'vue-i18n'

// 国际化
const { t } = useI18n()

interface Props {
  open: boolean
}

interface Emits {
  (e: 'update:open', value: boolean): void
  (e: 'success'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const authStore = useAuthStore()

// 响应式状态
const visible = ref(false)
const saving = ref(false)
const uploadingAvatar = ref(false)
const formRef = ref()
const avatarInputRef = ref<HTMLInputElement>()

// 表单数据
const formData = ref<UserInfo & { avatar?: string }>({
  uid: 0,
  user_name: '',
  role: 'user',
  avatar: ''
})

// 头像URL
const avatarUrl = ref('')

// 计算属性
const displayName = computed(() => formData.value.user_name || '用户')

const roleColor = computed(() => {
  switch (formData.value.role) {
    case 'admin': return 'red'
    case 'user': return 'blue'
    default: return 'default'
  }
})

const roleText = computed(() => {
  switch (formData.value.role) {
    case 'admin': return t('components_UserProfileModal.roleAdmin')
    case 'user': return t('components_UserProfileModal.roleUser')
    default: return t('components_UserProfileModal.roleUnknown')
  }
})

// 表单验证规则
const formRules = {
  user_name: [
    { required: true, message: t('components_UserProfileModal.usernamePlaceholder'), trigger: 'blur' },
    { min: 2, max: 20, message: t('components_UserProfileModal.usernameLength'), trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_\u4e00-\u9fa5]+$/, message: t('components_UserProfileModal.usernamePattern'), trigger: 'blur' }
  ]
}

// 监听props变化
watch(() => props.open, (newVal) => {
  visible.value = newVal
  if (newVal) {
    initForm()
  }
})

watch(visible, (newVal) => {
  emit('update:open', newVal)
})

// 初始化表单
const initForm = () => {
  const user = authStore.currentUser
  if (user) {
    formData.value = {
      uid: user.uid,
      user_name: user.user_name,
      role: user.role || 'user',
      avatar: user.avatar || ''
    }
    avatarUrl.value = user.avatar || ''
  }
}

// 触发头像上传
const triggerAvatarUpload = () => {
  avatarInputRef.value?.click()
}

// 处理头像上传
const handleAvatarUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  
  if (!file) return

  // 验证文件类型
  if (!file.type.startsWith('image/')) {
    message.error(t('components_UserProfileModal.selectImage'))
    return
  }

  // 验证文件大小（2MB）
  if (file.size > 2 * 1024 * 1024) {
    message.error(t('components_UserProfileModal.imageTooLarge'))
    return
  }

  try {
    uploadingAvatar.value = true

    // 读取文件为Base64
    const reader = new FileReader()
    reader.onload = (e) => {
      const base64 = e.target?.result as string
      avatarUrl.value = base64
      formData.value.avatar = base64
      message.success(t('components_UserProfileModal.uploadSuccess'))
    }
    reader.onerror = () => {
      message.error(t('components_UserProfileModal.readFailed'))
    }
    reader.readAsDataURL(file)

  } catch (error) {
    message.error(t('components_UserProfileModal.uploadFailed'))
  } finally {
    uploadingAvatar.value = false
    // 清空input，允许重复上传同一文件
    target.value = ''
  }
}

// 移除头像
const removeAvatar = () => {
  avatarUrl.value = ''
  formData.value.avatar = ''
  message.success(t('components_UserProfileModal.removeSuccess'))
}

// 保存用户信息
const handleSave = async () => {
  try {
    // 表单验证
    await formRef.value?.validate()

    saving.value = true

    // 调用更新API
    await authStore.updateUserProfile({
      user_name: formData.value.user_name,
      avatar: formData.value.avatar
    })

    message.success(t('components_UserProfileModal.updateSuccess'))
    visible.value = false
    emit('success')

  } catch (error: any) {
    if (error.errorFields) {
      // 表单验证错误
      message.error(t('components_UserProfileModal.checkInput'))
    } else {
      message.error(t('components_UserProfileModal.saveFailed'))
    }
  } finally {
    saving.value = false
  }
}

// 取消编辑
const handleCancel = () => {
  visible.value = false
  // 重置表单
  nextTick(() => {
    initForm()
  })
}
</script>

<style scoped>
.user-profile-form {
  padding: 8px 0;
}

/* 头像编辑区域 */
.avatar-section {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 20px 0;
  border-bottom: 1px solid #f0f0f0;
  margin-bottom: 24px;
}

.avatar-preview {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  overflow: hidden;
  border: 2px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fafafa;
}

.avatar-placeholder {
  font-size: 32px;
  font-weight: 600;
  color: #1890ff;
  background: linear-gradient(135deg, #1890ff, #40a9ff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 表单样式 */
.profile-form {
  margin-bottom: 24px;
}

.profile-form .ant-form-item {
  margin-bottom: 20px;
}

/* 上传提示 */
.upload-tips {
  background: #f6f8fa;
  border: 1px solid #e1e4e8;
  border-radius: 6px;
  padding: 16px;
  margin-top: 16px;
}

.upload-tips h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #24292e;
}

.upload-tips ul {
  margin: 0;
  padding-left: 20px;
}

.upload-tips li {
  font-size: 13px;
  color: #586069;
  line-height: 1.6;
  margin-bottom: 4px;
}

.upload-tips li:last-child {
  margin-bottom: 0;
}

/* 响应式设计 */
@media (max-width: 576px) {
  .avatar-section {
    flex-direction: column;
    text-align: center;
    gap: 16px;
  }
  
  .avatar-actions {
    flex-direction: row;
    justify-content: center;
  }
}
</style>
