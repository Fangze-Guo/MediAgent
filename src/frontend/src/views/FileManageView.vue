<template>
  <div class="file-browser">
    <a-layout>
      <a-layout-content class="content">
        <!-- 上栏工具栏 -->
        <div class="top-toolbar">
          <h2 class="title">管理我的数据</h2>
          <div class="top-actions">
            <a-button type="primary">
              <template #icon>
                <SearchOutlined />
              </template>
              查看公共数据
            </a-button>
          </div>
        </div>

        <!-- 下栏工具栏 -->
        <div class="bottom-toolbar">
          <a-button disabled>
            <template #icon>
              <ArrowLeftOutlined />
            </template>
            返回上级
          </a-button>
          <div class="right-actions">
            <a-button type="primary">
              <template #icon>
                <UploadOutlined />
              </template>
              上传文件
            </a-button>
            <a-button disabled>
              <template #icon>
                <DeleteOutlined />
              </template>
              批量删除 (0)
            </a-button>
            <div class="current-path">
              <span class="label">当前路径:</span>
              <a-tag color="blue">/</a-tag>
            </div>
          </div>
        </div>

        <!-- 文件列表容器 -->
        <div class="file-list-container">
          <a-table
              :data-source="dataSource"
              :columns="columns"
              :pagination="false"
              :scroll="{ y: 400 }"
              size="middle"
              class="file-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.dataIndex === 'name'">
                <div class="file-name-cell">
                  <span class="file-icon">{{ record.icon }}</span>
                  <span>{{ record.name }}</span>
                </div>
              </template>
              <template v-else-if="column.dataIndex === 'actions'">
                <div class="actions" v-if="!record.isFolder">
                  <a-button type="text" size="small" title="编辑">
                    <EditOutlined />
                  </a-button>
                  <a-button type="text" size="small" danger title="删除">
                    <DeleteOutlined />
                  </a-button>
                  <a-button type="text" size="small" title="下载">
                    <DownloadOutlined />
                  </a-button>
                </div>
              </template>
            </template>
          </a-table>
        </div>
      </a-layout-content>
    </a-layout>
  </div>
</template>

<script setup lang="ts">
import {
  ArrowLeftOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  SearchOutlined,
  UploadOutlined
} from '@ant-design/icons-vue'

// 表格列定义
const columns = [
  {
    title: '名称',
    dataIndex: 'name',
    key: 'name',
  },
  {
    title: '大小',
    dataIndex: 'size',
    key: 'size',
    width: 120,
  },
  {
    title: '日期',
    dataIndex: 'date',
    key: 'date',
    width: 150,
  },
  {
    title: '操作',
    dataIndex: 'actions',
    key: 'actions',
    width: 120,
  },
]

// 表格数据源
const dataSource = [
  {
    key: '1',
    icon: '📁',
    name: '文档',
    size: '-',
    date: '-',
    isFolder: true,
  },
  {
    key: '2',
    icon: '📄',
    name: '病历报告.pdf',
    size: '1.2 MB',
    date: '2023-10-15',
    isFolder: false,
  },
  {
    key: '3',
    icon: '📄',
    name: '检查结果.jpg',
    size: '2.1 MB',
    date: '2023-10-14',
    isFolder: false,
  },
  {
    key: '4',
    icon: '📄',
    name: '用药记录.txt',
    size: '50 KB',
    date: '2023-10-13',
    isFolder: false,
  },
  {
    key: '5',
    icon: '📄',
    name: '体检数据.xlsx',
    size: '3.5 MB',
    date: '2023-10-12',
    isFolder: false,
  },
  {
    key: '6',
    icon: '📄',
    name: '诊断说明.docx',
    size: '1.8 MB',
    date: '2023-10-11',
    isFolder: false,
  },
]
</script>

<style scoped>
.file-browser {
  background-color: #f0f2f5;
  border-radius: 8px;
  margin: 24px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.content {
  background: white;
  padding: 0;
  border-radius: 8px;
}

/* 工具栏通用样式 */
.top-toolbar,
.bottom-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid #f0f0f0;
}

.top-toolbar {
  background: #fafafa;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.bottom-toolbar {
  background: #fff;
}

.title {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
  color: #333;
}

/* 右侧操作容器 */
.right-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

/* 当前路径显示样式 */
.current-path {
  display: flex;
  align-items: center;
  gap: 8px;
}

.current-path .label {
  font-weight: 500;
  color: #666;
}

/* 文件列表容器 */
.file-list-container {
  padding: 0 24px 24px;
}

.file-table {
  border: 1px solid #f0f0f0;
  border-radius: 4px;
}

/* 文件名单元格 */
.file-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-icon {
  font-size: 16px;
}

/* 操作按钮 */
.actions {
  display: flex;
  gap: 8px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .file-browser {
    margin: 12px;
    padding: 16px;
  }

  .top-toolbar,
  .bottom-toolbar {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }

  .right-actions {
    width: 100%;
    justify-content: space-between;
  }

  .file-list-container {
    padding: 0 12px 16px;
  }
}
</style>
