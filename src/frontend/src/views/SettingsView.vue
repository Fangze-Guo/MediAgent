<template>
  <div class="settings-page">
    <div class="settings-header">
      <h1>设置</h1>
      <p>管理你的 MediAgent 偏好设置</p>
    </div>
    
    <div class="settings-content">
      <div class="settings-section">
        <h2>聊天设置</h2>
        <div class="setting-item">
          <label>自动滚动到底部</label>
          <input type="checkbox" checked />
        </div>
        <div class="setting-item">
          <label>消息时间显示</label>
          <select>
            <option>相对时间</option>
            <option>绝对时间</option>
          </select>
        </div>
      </div>
      
      <div class="settings-section">
        <h2>界面设置</h2>
        <div class="setting-item">
          <label>主题</label>
          <select>
            <option>浅色</option>
            <option>深色</option>
            <option>跟随系统</option>
          </select>
        </div>
      </div>
      
      <div class="settings-section">
        <h2>数据管理</h2>
        <div class="setting-item">
          <label>导出聊天记录</label>
          <button class="btn-secondary">导出</button>
        </div>
        <div class="setting-item">
          <label>清除所有数据</label>
          <button class="btn-danger">清除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// 静态展示，无需逻辑
</script>

<style scoped>
.settings-page {
  padding: 40px;
  max-width: 800px;
  margin: 0 auto;
  background: white;
  min-height: 100vh;
}

.settings-header {
  text-align: center;
  margin-bottom: 40px;
}

.settings-header h1 {
  color: #333;
  margin-bottom: 10px;
}

.settings-header p {
  color: #666;
  margin: 0;
}

.settings-content {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.settings-section {
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 24px;
}

.settings-section h2 {
  color: #333;
  margin: 0 0 20px 0;
  font-size: 18px;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
  border-bottom: 1px solid #f0f0f0;
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-item label {
  color: #555;
  font-weight: 500;
}

.setting-item input[type="checkbox"] {
  width: 20px;
  height: 20px;
}

.setting-item select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
  color: #333;
}

.btn-secondary {
  padding: 8px 16px;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-secondary:hover {
  background: #5a6268;
}

.btn-danger {
  padding: 8px 16px;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-danger:hover {
  background: #c82333;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .settings-page {
    padding: 20px;
  }
  
  .setting-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
}
</style>
