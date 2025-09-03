<template>
  <div class="chat-bg">
    <div class="chat-fixed">
      <a-layout class="chat-layout">
        <a-layout-header class="chat-header">
          <h2 class="chat-title">健康咨询</h2>
        </a-layout-header>
        <a-layout-content class="chat-messages">
          <div class="message ai">
            <div class="avatar ai-avatar">
              <a-icon type="robot" />
            </div>
            <div class="message-content">你好！我是 MediAgent AI，有什么可以帮助你的吗？</div>
          </div>
          <div class="message user">
            <div class="message-content">我想了解一下如何保持健康的生活方式</div>
            <div class="avatar user-avatar">
              <a-icon type="user" />
            </div>
          </div>
          <div class="message ai">
            <div class="avatar ai-avatar">
              <a-icon type="robot" />
            </div>
            <div class="message-content">保持健康的生活方式很重要！建议规律作息、均衡饮食、适量运动。每天保持7-8小时睡眠，多吃蔬菜水果，每周至少运动3-4次。</div>
          </div>
          <div class="message user">
            <div class="message-content">运动方面有什么具体建议吗？</div>
            <div class="avatar user-avatar">
              <a-icon type="user" />
            </div>
          </div>
          <div class="message ai">
            <div class="avatar ai-avatar">
              <a-icon type="robot" />
            </div>
            <div class="message-content">运动对身体很有好处！建议每天进行30分钟以上的中等强度运动，比如快走、慢跑、游泳或骑自行车。也可以尝试力量训练来增强肌肉。</div>
          </div>
        </a-layout-content>
        <a-layout-footer class="chat-input">
          <a-textarea 
            class="message-input"
            placeholder="输入消息，按 Enter 换行"
            :auto-size="{ minRows: 1, maxRows: 6 }"
          />
          <a-button 
            type="primary" 
            class="send-btn"
          >
            发送
          </a-button>
        </a-layout-footer>
      </a-layout>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
/* 背景容器：铺满内容区，负责居中内部固定宽度聊天卡片 */
.chat-bg {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: stretch;
  justify-content: center;
}

/* 居中容器：提供内边距与水平居中承载聊天布局 */
.chat-fixed {
  flex: 1;
  display: flex;
  align-items: stretch;
  justify-content: center;
  padding: 24px;
}

/* 聊天主卡片：目标宽度约 60%（含最小/最大宽度），高度跟随内容区 100% */
.chat-layout {
  width: min(60%, 980px);
  min-width: 640px;
  max-width: 980px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
}

/* 小屏策略：当空间不足时允许卡片压缩到更小宽度 */
@media (max-width: 720px) {
  .chat-layout {
    width: 100%;
    min-width: 360px;
  }
}

/* 顶部栏：固定 56px 高度，白色背景与底部分隔线 */
.chat-header {
  background: white;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  padding: 0 24px;
  height: 56px;
}

/* 顶部标题：字号/颜色/加粗 */
.chat-title {
  margin: 0;
  color: #333;
  font-size: 18px;
  font-weight: 600;
}

/* 消息列表：可滚动区域，撑满除头尾外的剩余高度 */
.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background-color: #f9f9f9;
}

/* 单条消息容器：最大宽度、圆角、内边距与布局 */
.message {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 18px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

/* 用户消息：靠右显示，头像在右侧 */
.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

/* AI 消息：靠左显示 */
.message.ai {
  align-self: flex-start;
}

/* 头像：尺寸、圆形、居中对齐与顶部微调 */
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 4px;
}

/* AI 头像：紫色渐变背景与白色图标 */
.ai-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

/* 用户头像：浅蓝背景与主色图标 */
.user-avatar {
  background: #e0efff;
  color: #165dff;
}

/* 消息文本：行高与换行策略 */
.message-content {
  line-height: 1.6;
  word-wrap: break-word;
  padding: 8px 0;
}

/* AI 气泡：白底轻阴影 */
.message.ai {
  background: #ffffff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

/* 用户气泡：紫色渐变与白色文字 */
.message.user {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
}

/* 输入区：底部工具栏容器 */
.chat-input {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  padding: 16px 24px;
  background: white;
  border-top: 1px solid #f0f0f0;
}

/* 文本域：占满剩余空间，支持自适应高度 */
.message-input {
  flex: 1;
}

/* 发送按钮：避免换行 */
.send-btn {
  white-space: nowrap;
}
</style>