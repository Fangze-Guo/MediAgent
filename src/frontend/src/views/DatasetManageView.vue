<template>
  <div class="dataset-manage">
    <div class="page-header">
      <h1 class="page-title">{{ t('views_DatasetManageView.title') }}</h1>
      <button class="btn-primary" @click="showCreateDialog = true">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
        {{ t('views_DatasetManageView.createButton') }}
      </button>
    </div>

    <!-- 数据集列表 -->
    <div class="dataset-list" v-if="datasets.length > 0">
      <div
        class="dataset-card"
        v-for="dataset in datasets"
        :key="dataset.id"
        @click="selectDataset(dataset)"
      >
        <div class="dataset-header">
          <div class="dataset-icon">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"
              ></path>
            </svg>
          </div>
          <div class="dataset-info">
            <h3 class="dataset-name">{{ dataset.dataset_name }}</h3>
            <p class="dataset-count">{{ t('views_DatasetManageView.caseCount', { count: dataset.case_count }) }}</p>
            <div class="dataset-status">
              <span 
                class="status-tag" 
                :class="dataset.has_data ? 'status-success' : 'status-warning'"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                </svg>
                {{ dataset.has_data ? t('views_DatasetManageView.dataUploaded') : t('views_DatasetManageView.dataNotUploaded') }}
              </span>
              <span 
                class="status-tag" 
                :class="dataset.has_description_file ? 'status-success' : 'status-warning'"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
                {{ dataset.has_description_file ? t('views_DatasetManageView.descriptionUploaded') : t('views_DatasetManageView.descriptionNotUploaded') }}
              </span>
            </div>
          </div>
          <div class="dataset-actions">
            <button
              class="btn-icon"
              @click.stop="viewDatasetFiles(dataset)"
:title="t('views_DatasetManageView.viewFiles')"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
            </button>
            <button
              class="btn-icon"
              @click.stop="editDataset(dataset)"
:title="t('views_DatasetManageView.edit')"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path
                  d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"
                ></path>
                <path
                  d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"
                ></path>
              </svg>
            </button>
            <button
              class="btn-icon btn-danger"
              @click.stop="confirmDeleteDataset(dataset)"
:title="t('views_DatasetManageView.delete')"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <polyline points="3 6 5 6 21 6"></polyline>
                <path
                  d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
                ></path>
              </svg>
            </button>
          </div>
        </div>

        <div class="dataset-body">
          <div class="data-tags">
            <span
              class="data-tag clinical"
              v-if="dataset.clinical_data_desc"
              :title="t('views_DatasetManageView.dataTypes.clinical')"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path
                  d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                ></path>
                <polyline points="14 2 14 8 20 8"></polyline>
              </svg>
              {{ t('views_DatasetManageView.dataTypes.clinical') }}
            </span>
            <span
              class="data-tag text"
              v-if="dataset.text_data_desc"
              :title="t('views_DatasetManageView.dataTypes.text')"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <line x1="17" y1="10" x2="3" y2="10"></line>
                <line x1="21" y1="6" x2="3" y2="6"></line>
                <line x1="21" y1="14" x2="3" y2="14"></line>
                <line x1="17" y1="18" x2="3" y2="18"></line>
              </svg>
              {{ t('views_DatasetManageView.dataTypes.text') }}
            </span>
            <span
              class="data-tag imaging"
              v-if="dataset.imaging_data_desc"
              :title="t('views_DatasetManageView.dataTypes.imaging')"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <polyline points="21 15 16 10 5 21"></polyline>
              </svg>
              {{ t('views_DatasetManageView.dataTypes.imaging') }}
            </span>
            <span
              class="data-tag pathology"
              v-if="dataset.pathology_data_desc"
              :title="t('views_DatasetManageView.dataTypes.pathology')"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              {{ t('views_DatasetManageView.dataTypes.pathology') }}
            </span>
            <span
              class="data-tag genomics"
              v-if="dataset.genomics_data_desc"
              :title="t('views_DatasetManageView.dataTypes.genomics')"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path d="M12 2v20M2 12h20"></path>
              </svg>
              {{ t('views_DatasetManageView.dataTypes.genomics') }}
            </span>
            <span
              class="data-tag annotation"
              v-if="dataset.annotation_desc"
              :title="t('views_DatasetManageView.dataTypes.annotation')"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path
                  d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
                ></path>
              </svg>
              {{ t('views_DatasetManageView.dataTypes.annotation') }}
            </span>
          </div>

          <div class="dataset-notes" v-if="dataset.notes">
            <span>{{ dataset.notes }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div class="empty-state" v-else-if="!loading">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="64"
        height="64"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path
          d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"
        ></path>
      </svg>
      <p>{{ t('views_DatasetManageView.emptyState') }}</p>
    </div>

    <!-- 加载状态 -->
    <div class="loading-state" v-if="loading">
      <div class="spinner"></div>
      <p>{{ t('views_DatasetManageView.loading') }}</p>
    </div>

    <!-- 创建/编辑数据集对话框 -->
    <div
      class="modal"
      v-if="showCreateDialog || showEditDialog"
      @click.self="closeDialogs"
    >
      <div class="modal-content">
        <div class="modal-header">
          <h2>{{ showEditDialog ? t('views_DatasetManageView.dialog.editTitle') : t('views_DatasetManageView.dialog.createTitle') }}</h2>
          <button class="btn-close" @click="closeDialogs">×</button>
        </div>
        <div class="modal-body">
          <!-- 基本信息 -->
          <div class="form-section">
            <h4 class="section-title">{{ t('views_DatasetManageView.dialog.basicInfo') }}</h4>
            <div class="form-row">
              <div class="form-group">
                <label>{{ t('views_DatasetManageView.dialog.datasetName') }} <span class="required">*</span></label>
                <input
                  v-model="formData.dataset_name"
                  type="text"
                  :disabled="showEditDialog"
                />
              </div>
              <div class="form-group form-group-small">
                <label>{{ t('views_DatasetManageView.dialog.quantity') }}</label>
                <input
                  v-model.number="formData.case_count"
                  type="number"
                  min="0"
                  placeholder="0"
                />
              </div>
            </div>
          </div>

          <!-- 数据描述 -->
          <div class="form-section">
            <h4 class="section-title">{{ t('views_DatasetManageView.dialog.dataDescription') }}</h4>
            <div class="form-group">
              <label>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  style="vertical-align: middle"
                >
                  <path
                    d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                  ></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
                {{ t('views_DatasetManageView.descriptions.clinical') }}
              </label>
              <textarea
                v-model="formData.clinical_data_desc"
                rows="2"
                :placeholder="t('views_DatasetManageView.placeholders.clinical')"
              ></textarea>
            </div>
            <div class="form-group">
              <label>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  style="vertical-align: middle"
                >
                  <line x1="17" y1="10" x2="3" y2="10"></line>
                  <line x1="21" y1="6" x2="3" y2="6"></line>
                </svg>
                {{ t('views_DatasetManageView.descriptions.text') }}
              </label>
              <textarea
                v-model="formData.text_data_desc"
                rows="2"
                :placeholder="t('views_DatasetManageView.placeholders.text')"
              ></textarea>
            </div>
            <div class="form-group">
              <label>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  style="vertical-align: middle"
                >
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                  <circle cx="8.5" cy="8.5" r="1.5"></circle>
                </svg>
                {{ t('views_DatasetManageView.descriptions.imaging') }}
              </label>
              <textarea
                v-model="formData.imaging_data_desc"
                rows="2"
                :placeholder="t('views_DatasetManageView.placeholders.imaging')"
              ></textarea>
            </div>
            <div class="form-group">
              <label>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  style="vertical-align: middle"
                >
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                </svg>
                {{ t('views_DatasetManageView.descriptions.pathology') }}
              </label>
              <textarea
                v-model="formData.pathology_data_desc"
                rows="2"
                :placeholder="t('views_DatasetManageView.placeholders.pathology')"
              ></textarea>
            </div>
            <div class="form-group">
              <label>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  style="vertical-align: middle"
                >
                  <path d="M12 2v20M2 12h20"></path>
                </svg>
                {{ t('views_DatasetManageView.descriptions.genomics') }}
              </label>
              <textarea
                v-model="formData.genomics_data_desc"
                rows="2"
                :placeholder="t('views_DatasetManageView.placeholders.genomics')"
              ></textarea>
            </div>
            <div class="form-group">
              <label>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  style="vertical-align: middle"
                >
                  <path
                    d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
                  ></path>
                </svg>
                {{ t('views_DatasetManageView.descriptions.annotation') }}
              </label>
              <textarea
                v-model="formData.annotation_desc"
                rows="2"
                :placeholder="t('views_DatasetManageView.placeholders.annotation')"
              ></textarea>
            </div>
          </div>

          <!-- 其他信息 -->
          <div class="form-section">
            <h4 class="section-title">{{ t('views_DatasetManageView.dialog.otherInfo') }}</h4>
            <div class="form-group">
              <label>{{ t('views_DatasetManageView.dialog.remarks') }}</label>
              <textarea
                v-model="formData.notes"
                rows="2"
                :placeholder="t('views_DatasetManageView.placeholders.remarks')"
              ></textarea>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="closeDialogs">{{ t('views_DatasetManageView.dialog.cancel') }}</button>
          <button
            class="btn-primary"
            @click="showEditDialog ? updateDatasetInfo() : createDatasetInfo()"
            :disabled="!formData.dataset_name"
          >
            {{ showEditDialog ? t('views_DatasetManageView.dialog.save') : t('views_DatasetManageView.dialog.create') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 数据集详情对话框（含文件上传） -->
    <div
      class="modal"
      v-if="showDetailDialog"
      @click.self="showDetailDialog = false"
    >
      <div class="modal-content modal-large">
        <div class="modal-header">
          <div class="header-content">
            <h2>{{ selectedDataset?.dataset_name }}</h2>
            <div class="dataset-status-inline">
              <span 
                class="status-tag" 
                :class="selectedDataset?.has_data ? 'status-success' : 'status-warning'"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                </svg>
                {{ selectedDataset?.has_data ? t('views_DatasetManageView.dataUploaded') : t('views_DatasetManageView.dataNotUploaded') }}
              </span>
              <span 
                class="status-tag" 
                :class="selectedDataset?.has_description_file ? 'status-success' : 'status-warning'"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
                {{ selectedDataset?.has_description_file ? t('views_DatasetManageView.descriptionUploaded') : t('views_DatasetManageView.descriptionNotUploaded') }}
              </span>
            </div>
          </div>
          <button class="btn-close" @click="showDetailDialog = false">×</button>
        </div>
        <div class="modal-body">
          <!-- 基本统计 -->
          <div class="stats-card">
            <div class="stat-item">
              <div class="stat-icon cases">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                  <circle cx="12" cy="7" r="4"></circle>
                </svg>
              </div>
              <div class="stat-content">
                <div class="stat-label">{{ t('views_DatasetManageView.dialog.quantity') }}</div>
                <div class="stat-value">{{ selectedDataset?.case_count }}</div>
              </div>
            </div>
          </div>

          <!-- 数据描述卡片 -->
          <div class="detail-section">
            <h3 class="section-title-detail">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path
                  d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"
                ></path>
                <polyline points="13 2 13 9 20 9"></polyline>
              </svg>
              {{ t('views_DatasetManageView.dialog.dataDescription') }}
            </h3>

            <div class="data-cards">
              <!-- 临床数据 -->
              <div
                class="data-card clinical"
                v-if="selectedDataset?.clinical_data_desc"
              >
                <div class="data-card-header">
                  <div class="data-card-icon">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                    >
                      <path
                        d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                      ></path>
                      <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                  </div>
                  <h4>{{ t('views_DatasetManageView.dataTypes.clinical') }}</h4>
                </div>
                <p class="data-card-content">
                  {{ selectedDataset.clinical_data_desc }}
                </p>
              </div>

              <!-- 文本数据 -->
              <div
                class="data-card text"
                v-if="selectedDataset?.text_data_desc"
              >
                <div class="data-card-header">
                  <div class="data-card-icon">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                    >
                      <line x1="17" y1="10" x2="3" y2="10"></line>
                      <line x1="21" y1="6" x2="3" y2="6"></line>
                      <line x1="21" y1="14" x2="3" y2="14"></line>
                      <line x1="17" y1="18" x2="3" y2="18"></line>
                    </svg>
                  </div>
                  <h4>{{ t('views_DatasetManageView.dataTypes.text') }}</h4>
                </div>
                <p class="data-card-content">
                  {{ selectedDataset.text_data_desc }}
                </p>
              </div>

              <!-- 影像数据 -->
              <div
                class="data-card imaging"
                v-if="selectedDataset?.imaging_data_desc"
              >
                <div class="data-card-header">
                  <div class="data-card-icon">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                    >
                      <rect
                        x="3"
                        y="3"
                        width="18"
                        height="18"
                        rx="2"
                        ry="2"
                      ></rect>
                      <circle cx="8.5" cy="8.5" r="1.5"></circle>
                      <polyline points="21 15 16 10 5 21"></polyline>
                    </svg>
                  </div>
                  <h4>{{ t('views_DatasetManageView.dataTypes.imaging') }}</h4>
                </div>
                <p class="data-card-content">
                  {{ selectedDataset.imaging_data_desc }}
                </p>
              </div>

              <!-- 病理数据 -->
              <div
                class="data-card pathology"
                v-if="selectedDataset?.pathology_data_desc"
              >
                <div class="data-card-header">
                  <div class="data-card-icon">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                    >
                      <circle cx="12" cy="12" r="10"></circle>
                      <line x1="12" y1="8" x2="12" y2="12"></line>
                      <line x1="12" y1="16" x2="12.01" y2="16"></line>
                    </svg>
                  </div>
                  <h4>{{ t('views_DatasetManageView.dataTypes.pathology') }}</h4>
                </div>
                <p class="data-card-content">
                  {{ selectedDataset.pathology_data_desc }}
                </p>
              </div>

              <!-- 基因组数据 -->
              <div
                class="data-card genomics"
                v-if="selectedDataset?.genomics_data_desc"
              >
                <div class="data-card-header">
                  <div class="data-card-icon">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                    >
                      <path d="M12 2v20M2 12h20"></path>
                    </svg>
                  </div>
                  <h4>{{ t('views_DatasetManageView.dataTypes.genomics') }}</h4>
                </div>
                <p class="data-card-content">
                  {{ selectedDataset.genomics_data_desc }}
                </p>
              </div>

              <!-- 标注信息 -->
              <div
                class="data-card annotation"
                v-if="selectedDataset?.annotation_desc"
              >
                <div class="data-card-header">
                  <div class="data-card-icon">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                    >
                      <path
                        d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
                      ></path>
                    </svg>
                  </div>
                  <h4>{{ t('views_DatasetManageView.dataTypes.annotation') }}</h4>
                </div>
                <p class="data-card-content">
                  {{ selectedDataset.annotation_desc }}
                </p>
              </div>

              <!-- 备注 -->
              <div class="data-card notes" v-if="selectedDataset?.notes">
                <div class="data-card-header">
                  <div class="data-card-icon">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                    >
                      <circle cx="12" cy="12" r="10"></circle>
                      <line x1="12" y1="16" x2="12" y2="12"></line>
                      <line x1="12" y1="8" x2="12.01" y2="8"></line>
                    </svg>
                  </div>
                  <h4>{{ t('views_DatasetManageView.dialog.remarks') }}</h4>
                </div>
                <p class="data-card-content">{{ selectedDataset.notes }}</p>
              </div>
            </div>
          </div>

          <!-- 文件上传区域 -->
          <div class="detail-section">
            <h3 class="section-title-detail">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
              上传文件
            </h3>
            <div
              class="upload-area"
              :class="{ 'drag-over': isDragging }"
              @drop.prevent="handleDrop"
              @dragover.prevent="isDragging = true"
              @dragleave.prevent="isDragging = false"
            >
              <input
                type="file"
                ref="fileInput"
                multiple
                webkitdirectory
                @change="handleFileSelect"
                style="display: none"
              />
              <input
                type="file"
                ref="fileInputSingle"
                multiple
                @change="handleFileSelect"
                style="display: none"
              />
              <div class="upload-icon">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="17 8 12 3 7 8"></polyline>
                  <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
              </div>
              <p class="upload-text">
                拖拽文件/文件夹到此处或
                <button class="btn-link" @click="triggerFileSelect">
                  选择文件
                </button>
                /
                <button class="btn-link" @click="triggerFolderSelect">
                  选择文件夹
                </button>
              </p>
              <p class="upload-hint">
                支持拖拽多个文件夹同时上传，或多次点击"选择文件夹"添加。文件将按文件夹分组显示，保持原有目录结构。
              </p>
            </div>

            <!-- 待上传文件列表 - 按文件夹分组显示 -->
            <div class="file-list" v-if="uploadFiles.length > 0">
              <div class="file-list-header">
                <h4>待上传文件 ({{ uploadFiles.length }} 个文件, {{ Object.keys(groupedFiles).length }} 个文件夹)</h4>
                <div class="file-list-actions">
                  <button class="btn-secondary" @click="clearAllFiles" :disabled="uploading">
                    清空列表
                  </button>
                  <button
                    class="btn-primary"
                    @click="uploadAllFiles"
                    :disabled="uploading"
                  >
                    {{ uploading ? "上传中..." : "开始上传" }}
                  </button>
                </div>
              </div>
              
              <!-- 按文件夹分组显示 -->
              <div class="folder-groups">
                <div 
                  class="folder-group"
                  v-for="(files, folderName) in groupedFiles"
                  :key="folderName"
                >
                  <div class="folder-header" @click="toggleFolder(folderName)">
                    <div class="folder-info">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                        class="folder-icon"
                      >
                        <path v-if="expandedFolders[folderName]" d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                        <path v-else d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                      </svg>
                      <span class="folder-name">{{ folderName || '根目录' }}</span>
                      <span class="folder-count">({{ files.length }} 个文件)</span>
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                        class="expand-icon"
                        :class="{ expanded: expandedFolders[folderName] }"
                      >
                        <polyline points="6 9 12 15 18 9"></polyline>
                      </svg>
                    </div>
                    <button 
                      class="btn-icon btn-danger" 
                      @click.stop="removeFolder(folderName)"
                      title="删除整个文件夹"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                      </svg>
                    </button>
                  </div>
                  
                  <!-- 文件列表（可折叠） -->
                  <div class="folder-files" v-show="expandedFolders[folderName]">
                    <div class="folder-files-container">
                      <div
                        class="file-item"
                        v-for="(file, index) in files"
                        :key="index"
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="2"
                          class="file-icon"
                        >
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                          <polyline points="14 2 14 8 20 8"></polyline>
                        </svg>
                        <span class="file-name" :title="file.relativePath">{{ getFileName(file.relativePath) }}</span>
                        <span class="file-size">{{ formatFileSize(file.file.size) }}</span>
                        <button class="btn-icon btn-danger" @click="removeFileFromFolder(folderName, index)">
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="12"
                            height="12"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                          >
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- CSV 描述文件上传 -->
            <div class="section-card" style="margin-top: 24px">
              <h3 class="section-title">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                  <line x1="16" y1="13" x2="8" y2="13"></line>
                  <line x1="16" y1="17" x2="8" y2="17"></line>
                  <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
                上传 CSV 描述文件
                <span v-if="selectedDataset?.has_description_file" class="status-badge">
                  已上传
                </span>
              </h3>
              
              <div class="csv-upload-area">
                <input
                  type="file"
                  ref="csvFileInput"
                  accept=".csv"
                  @change="handleCsvFileSelect"
                  style="display: none"
                />
                
                <div class="csv-info" v-if="selectedDataset?.has_description_file">
                  <div class="info-item">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                    >
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                      <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                    <span>{{ selectedDataset.description_file_path }}</span>
                  </div>
                </div>

                <div class="csv-upload-content">
                  <p class="csv-description">
                    上传数据集的详细描述文件（CSV 格式），该文件将保存为
                    <code>{{ selectedDataset?.id }}.csv</code>
                  </p>
                  
                  <div class="csv-file-preview" v-if="csvFile">
                    <div class="file-preview-item">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="20"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                      </svg>
                      <div class="file-info">
                        <span class="file-name">{{ csvFile.name }}</span>
                        <span class="file-size">{{ formatFileSize(csvFile.size) }}</span>
                      </div>
                      <button class="btn-icon btn-danger" @click="removeCsvFile">
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="2"
                        >
                          <line x1="18" y1="6" x2="6" y2="18"></line>
                          <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                      </button>
                    </div>
                  </div>

                  <div class="csv-actions">
                    <button class="btn-secondary" @click="triggerCsvFileSelect">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                      </svg>
                      选择 CSV 文件
                    </button>
                    <button
                      v-if="csvFile"
                      class="btn-primary"
                      @click="uploadCsvFile"
                      :disabled="csvUploading"
                    >
                      {{ csvUploading ? "上传中..." : "上传描述文件" }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 文件浏览模态框 -->
    <div
      class="modal"
      v-if="showFilesDialog"
      @click.self="showFilesDialog = false"
    >
      <div class="modal-content modal-large">
        <div class="modal-header file-browser-header">
          <div class="header-title-wrapper">
            <div class="header-icon">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path
                  d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"
                ></path>
              </svg>
            </div>
            <div class="header-text">
              <h2>{{ viewingDataset?.dataset_name }}</h2>
              <span class="header-subtitle">浏览数据集文件</span>
            </div>
          </div>
          <button class="btn-close" @click="showFilesDialog = false">×</button>
        </div>
        <div class="modal-body">
          <!-- 当前路径 -->
          <div class="file-breadcrumb">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path
                d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"
              ></path>
            </svg>
            <span class="breadcrumb-path">{{ currentFilePath || "/" }}</span>
            <button
              v-if="currentFilePath && currentFilePath !== '.'"
              class="btn-back"
              @click="goBackFolder"
              title="返回上级"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <line x1="19" y1="12" x2="5" y2="12"></line>
                <polyline points="12 19 5 12 12 5"></polyline>
              </svg>
              返回上级
            </button>
          </div>

          <!-- 文件列表 -->
          <div v-if="filesLoading" class="files-loading">
            <div class="spinner"></div>
            <p>加载中...</p>
          </div>

          <div v-else-if="datasetFiles.length === 0" class="empty-files">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1"
            >
              <path
                d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"
              ></path>
            </svg>
            <p>该文件夹为空</p>
          </div>

          <div v-else class="files-list-container">
            <!-- 表头 -->
            <div class="files-list-header">
              <div class="header-col col-name">名称</div>
              <div class="header-col col-size">大小</div>
              <div class="header-col col-time">修改时间</div>
            </div>
            
            <!-- 文件列表 -->
            <div class="files-list">
              <div
                v-for="file in datasetFiles"
                :key="file.id"
                class="file-list-item"
                :class="{ 'is-directory': file.isDirectory, 'is-file': !file.isDirectory }"
                @click="file.isDirectory ? openFolder(file) : null"
              >
                <div class="file-col col-name">
                  <div class="file-icon-wrapper">
                    <!-- 文件夹图标 -->
                    <svg
                      v-if="file.isDirectory"
                      xmlns="http://www.w3.org/2000/svg"
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      class="icon-folder"
                    >
                      <path
                        d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"
                      ></path>
                    </svg>
                    <!-- 文件图标 -->
                    <svg
                      v-else
                      xmlns="http://www.w3.org/2000/svg"
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      class="icon-file"
                    >
                      <path
                        d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"
                      ></path>
                      <polyline points="13 2 13 9 20 9"></polyline>
                    </svg>
                  </div>
                  <span class="file-name-text" :title="file.name">{{ file.name }}</span>
                </div>
                <div class="file-col col-size">
                  <span v-if="!file.isDirectory">{{ formatFileSize(file.size) }}</span>
                  <span v-else class="folder-indicator">—</span>
                </div>
                <div class="file-col col-time">
                  {{ formatTime(file.modifiedTime) }}
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="showFilesDialog = false">
            {{ t('common.close') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useI18n } from "vue-i18n";
import {
  getDatasetList,
  createDataset,
  updateDataset,
  deleteDataset,
  uploadFilesToDataset,
  uploadDescriptionFile,
  type DatasetInfo,
  type CreateDatasetRequest,
  type UpdateDatasetRequest,
} from "@/apis/dataset";
import { getDataSetFiles, type FileInfo } from "@/apis/files";
import { useAuthStore } from "@/store/auth";

const authStore = useAuthStore();
const { t } = useI18n();

// 状态
const datasets = ref<DatasetInfo[]>([]);
const loading = ref(false);
const showCreateDialog = ref(false);
const showEditDialog = ref(false);
const showDetailDialog = ref(false);
const selectedDataset = ref<DatasetInfo | null>(null);
const isDragging = ref(false);
const uploadFiles = ref<File[]>([]);
const uploading = ref(false);
const fileInput = ref<HTMLInputElement>();
const fileInputSingle = ref<HTMLInputElement>();
const expandedFolders = ref<Record<string, boolean>>({});  // 控制文件夹展开/折叠

// CSV 描述文件上传相关状态
const csvFile = ref<File | null>(null);
const csvUploading = ref(false);
const csvFileInput = ref<HTMLInputElement>();

// 文件浏览相关状态
const showFilesDialog = ref(false);
const viewingDataset = ref<DatasetInfo | null>(null);
const datasetFiles = ref<FileInfo[]>([]);
const filesLoading = ref(false);
const currentFilePath = ref("");

// 表单数据
const formData = ref<CreateDatasetRequest>({
  dataset_name: "",
  case_count: 0,
  clinical_data_desc: "",
  text_data_desc: "",
  imaging_data_desc: "",
  pathology_data_desc: "",
  genomics_data_desc: "",
  annotation_desc: "",
  notes: "",
});

// 计算属性：按文件夹分组文件
const groupedFiles = computed(() => {
  const groups: Record<string, Array<{ file: File; relativePath: string }>> = {};
  
  uploadFiles.value.forEach((file) => {
    const relativePath = (file as any).webkitRelativePath || file.name;
    const parts = relativePath.split('/');
    
    // 获取顶级文件夹名（如果有路径的话）
    const folderName = parts.length > 1 ? parts[0] : '';
    
    if (!groups[folderName]) {
      groups[folderName] = [];
      // 默认展开新添加的文件夹
      expandedFolders.value[folderName] = true;
    }
    
    groups[folderName].push({
      file,
      relativePath
    });
  });
  
  // 输出分组摘要
  if (uploadFiles.value.length > 0) {
    console.log(`📁 文件分组: ${Object.keys(groups).length} 个文件夹, ${uploadFiles.value.length} 个文件`);
  }
  
  return groups;
});

// 加载数据集列表
const loadDatasets = async () => {
  loading.value = true;
  try {
    const response = await getDatasetList();
    if (response.data.code === 200) {
      datasets.value = response.data.data;
    }
  } catch (error) {
    console.error("加载数据集列表失败:", error);
    alert("加载数据集列表失败");
  } finally {
    loading.value = false;
  }
};

// 创建数据集
const createDatasetInfo = async () => {
  if (!formData.value.dataset_name) {
    alert("请输入数据集名称");
    return;
  }

  try {
    const response = await createDataset(formData.value);
    if (response.data.code === 200) {
      alert("创建成功");
      closeDialogs();
      await loadDatasets();
    } else {
      alert(response.data.message || "创建失败");
    }
  } catch (error: any) {
    console.error("创建数据集失败:", error);
    alert(error.message || "创建失败");
  }
};

// 编辑数据集
const editDataset = (dataset: DatasetInfo) => {
  selectedDataset.value = dataset;
  formData.value = {
    dataset_name: dataset.dataset_name,
    case_count: dataset.case_count,
    clinical_data_desc: dataset.clinical_data_desc || "",
    text_data_desc: dataset.text_data_desc || "",
    imaging_data_desc: dataset.imaging_data_desc || "",
    pathology_data_desc: dataset.pathology_data_desc || "",
    genomics_data_desc: dataset.genomics_data_desc || "",
    annotation_desc: dataset.annotation_desc || "",
    notes: dataset.notes || "",
  };
  showEditDialog.value = true;
};

// 更新数据集
const updateDatasetInfo = async () => {
  if (!selectedDataset.value) return;

  try {
    const updateData: UpdateDatasetRequest = {
      id: selectedDataset.value.id!,
      ...formData.value,
    };
    const response = await updateDataset(updateData);
    if (response.data.code === 200) {
      alert("更新成功");
      closeDialogs();
      await loadDatasets();
    } else {
      alert(response.data.message || "更新失败");
    }
  } catch (error: any) {
    console.error("更新数据集失败:", error);
    alert(error.message || "更新失败");
  }
};

// 确认删除数据集
const confirmDeleteDataset = (dataset: DatasetInfo) => {
  if (
    confirm(
      `确定要删除数据集 "${dataset.dataset_name}" 吗？此操作将删除数据集及其所有文件，不可恢复！`
    )
  ) {
    deleteDatasetInfo(dataset.id!);
  }
};

// 删除数据集
const deleteDatasetInfo = async (datasetId: number) => {
  try {
    const response = await deleteDataset(datasetId);
    if (response.data.code === 200) {
      alert("删除成功");
      await loadDatasets();
    } else {
      alert(response.data.message || "删除失败");
    }
  } catch (error: any) {
    console.error("删除数据集失败:", error);
    alert(error.message || "删除失败");
  }
};

// 选择数据集（显示详情和上传界面）
const selectDataset = (dataset: DatasetInfo) => {
  selectedDataset.value = dataset;
  showDetailDialog.value = true;
  uploadFiles.value = [];
  csvFile.value = null;
};

// 查看数据集文件
const viewDatasetFiles = async (dataset: DatasetInfo) => {
  viewingDataset.value = dataset;
  showFilesDialog.value = true;
  currentFilePath.value = `private/${authStore.currentUser?.uid}/dataset/${dataset.dataset_name}`;
  await loadDatasetFiles();
};

// 加载数据集文件
const loadDatasetFiles = async () => {
  if (!currentFilePath.value) return;

  filesLoading.value = true;
  try {
    const response = await getDataSetFiles(currentFilePath.value);
    if (response.code === 200) {
      datasetFiles.value = response.data.files;
    }
  } catch (error) {
    console.error("加载文件列表失败:", error);
    alert("加载文件列表失败");
  } finally {
    filesLoading.value = false;
  }
};

// 打开文件夹
const openFolder = async (file: FileInfo) => {
  if (!file.isDirectory) return;
  currentFilePath.value = file.path;
  await loadDatasetFiles();
};

// 返回上级文件夹
const goBackFolder = async () => {
  if (!currentFilePath.value || currentFilePath.value === ".") return;

  // 提取上级路径
  const pathParts = currentFilePath.value.split("/");
  pathParts.pop();
  currentFilePath.value = pathParts.length > 0 ? pathParts.join("/") : ".";

  await loadDatasetFiles();
};

// 格式化时间
const formatTime = (timeStr: string): string => {
  try {
    const date = new Date(timeStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      const hours = Math.floor(diff / (1000 * 60 * 60));
      if (hours === 0) {
        const minutes = Math.floor(diff / (1000 * 60));
        return minutes === 0 ? "刚刚" : `${minutes}分钟前`;
      }
      return `${hours}小时前`;
    } else if (days < 7) {
      return `${days}天前`;
    } else {
      return date.toLocaleDateString("zh-CN");
    }
  } catch {
    return timeStr;
  }
};

// 触发文件选择
const triggerFileSelect = () => {
  fileInputSingle.value?.click();
};

// 触发文件夹选择
const triggerFolderSelect = () => {
  fileInput.value?.click();
};

// 处理文件选择
const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files) {
    uploadFiles.value = [...uploadFiles.value, ...Array.from(target.files)];
    // 重置input的值，允许重复选择相同的文件夹
    target.value = '';
  }
};

// 递归读取文件夹中的所有文件（带路径信息）
const readDirectoryRecursive = async (entry: any, basePath: string): Promise<File[]> => {
  const files: File[] = [];

  if (entry.isFile) {
    // 如果是文件，直接获取并附加路径信息
    const file = await new Promise<File>((resolve) => {
      entry.file((file: File) => resolve(file));
    });
    
    // 使用 try-catch 确保属性设置成功
    const relativePath = `${basePath}/${file.name}`;
    try {
      Object.defineProperty(file, 'webkitRelativePath', {
        writable: true,
        configurable: true,
        value: relativePath
      });
    } catch (e) {
      console.warn(`无法设置 webkitRelativePath: ${file.name}`, e);
      // 如果无法设置属性，尝试使用扩展对象
      (file as any).webkitRelativePath = relativePath;
    }
    
    files.push(file);
  } else if (entry.isDirectory) {
    // 如果是文件夹，递归读取
    const dirReader = entry.createReader();
    const newPath = `${basePath}/${entry.name}`;
    
    // readEntries 每次最多返回100个条目，需要循环调用直到返回空数组
    let entries: any[] = [];
    let batch: any[] = [];
    
    do {
      batch = await new Promise<any[]>((resolve) => {
        dirReader.readEntries((results: any[]) => resolve(results));
      });
      entries = entries.concat(batch);
    } while (batch.length > 0);

    // 递归处理每个条目
    for (const childEntry of entries) {
      const childFiles = await readDirectoryRecursive(childEntry, newPath);
      files.push(...childFiles);
    }
  }

  return files;
};

// 读取入口（文件或文件夹）
const readEntry = async (entry: any): Promise<File[]> => {
  if (entry.isFile) {
    // 单个文件：路径就是文件名
    const file = await new Promise<File>((resolve) => {
      entry.file((file: File) => resolve(file));
    });
    
    try {
      Object.defineProperty(file, 'webkitRelativePath', {
        writable: true,
        configurable: true,
        value: file.name
      });
    } catch (e) {
      (file as any).webkitRelativePath = file.name;
    }
    
    return [file];
  } else if (entry.isDirectory) {
    // 文件夹：使用文件夹名称作为基础路径
    const dirReader = entry.createReader();
    const files: File[] = [];
    
    // readEntries 每次最多返回100个条目，需要循环调用
    let entries: any[] = [];
    let batch: any[] = [];
    
    do {
      batch = await new Promise<any[]>((resolve) => {
        dirReader.readEntries((results: any[]) => resolve(results));
      });
      entries = entries.concat(batch);
    } while (batch.length > 0);

    // 递归处理文件夹内的每个条目
    for (const childEntry of entries) {
      const childFiles = await readDirectoryRecursive(childEntry, entry.name);
      files.push(...childFiles);
    }
    
    return files;
  }
  
  return [];
};

// 处理拖拽上传（支持文件夹）
const handleDrop = async (event: DragEvent) => {
  isDragging.value = false;

  if (!event.dataTransfer) return;

  const items = event.dataTransfer.items;
  if (items) {
    const itemCount = items.length;
    console.log(`📥 拖拽了 ${itemCount} 个项目`);
    
    // ⚠️ 重要：DataTransferItemList 在异步操作后会失效
    // 必须先同步提取所有 entries，再进行异步处理
    const entries: any[] = [];
    for (let i = 0; i < itemCount; i++) {
      const item = items[i];
      if (item.kind === "file") {
        const entry = item.webkitGetAsEntry();
        if (entry) {
          entries.push(entry);
        }
      }
    }
    
    if (entries.length === 0) {
      console.warn('⚠ 没有找到有效的文件或文件夹');
      return;
    }
    
    console.log(`📋 开始处理 ${entries.length} 个项目...`);
    
    // 现在进行异步处理
    const allFiles: File[] = [];
    for (let i = 0; i < entries.length; i++) {
      try {
        const entry = entries[i];
        const files = await readEntry(entry);
        console.log(`  ✓ ${entry.name}: ${files.length} 个文件`);
        allFiles.push(...files);
      } catch (error) {
        console.error(`❌ 处理 ${entries[i].name} 时出错:`, error);
        // 继续处理下一个项目
      }
    }

    console.log(`✅ 完成！共读取 ${allFiles.length} 个文件\n`);
    uploadFiles.value = [...uploadFiles.value, ...allFiles];
  } else if (event.dataTransfer.files) {
    // 降级方案：只支持文件
    console.log('使用降级方案读取文件');
    uploadFiles.value = [
      ...uploadFiles.value,
      ...Array.from(event.dataTransfer.files),
    ];
  }
};

// 清空所有文件
const clearAllFiles = () => {
  uploadFiles.value = [];
  expandedFolders.value = {};
};

// 切换文件夹展开/折叠
const toggleFolder = (folderName: string | number) => {
  const key = String(folderName);
  expandedFolders.value[key] = !expandedFolders.value[key];
};

// 删除整个文件夹
const removeFolder = (folderName: string | number) => {
  const key = String(folderName);
  uploadFiles.value = uploadFiles.value.filter((file) => {
    const relativePath = (file as any).webkitRelativePath || file.name;
    const parts = relativePath.split('/');
    const topFolder = parts.length > 1 ? parts[0] : '';
    return topFolder !== key;
  });
  delete expandedFolders.value[key];
};

// 从文件夹中删除单个文件
const removeFileFromFolder = (folderName: string | number, index: number) => {
  const key = String(folderName);
  const group = groupedFiles.value[key];
  if (group && group[index]) {
    const fileToRemove = group[index].file;
    const fileIndex = uploadFiles.value.indexOf(fileToRemove);
    if (fileIndex !== -1) {
      uploadFiles.value.splice(fileIndex, 1);
    }
  }
};

// 从路径中提取文件名
const getFileName = (relativePath: string): string => {
  const parts = relativePath.split('/');
  return parts[parts.length - 1];
};

// 上传所有文件
const uploadAllFiles = async () => {
  if (!selectedDataset.value || uploadFiles.value.length === 0) return;

  // 调试日志
  console.log('准备上传文件数量:', uploadFiles.value.length);
  uploadFiles.value.forEach((file, index) => {
    console.log(`文件 ${index + 1}:`, file.name, '大小:', file.size, 'File对象:', file);
  });

  uploading.value = true;
  try {
    const response = await uploadFilesToDataset(
      selectedDataset.value.id!,
      uploadFiles.value
    );
    if (response.data.code === 200) {
      alert(`成功上传 ${response.data.data.uploaded_count} 个文件`);
      uploadFiles.value = [];
      // 更新数据集列表以反映新的案例数
      await loadDatasets();
      // 更新选中的数据集信息
      const updated = datasets.value.find(
        (d) => d.id === selectedDataset.value?.id
      );
      if (updated) {
        selectedDataset.value = updated;
      }
    } else {
      alert(response.data.message || "上传失败");
    }
  } catch (error: any) {
    console.error("上传文件失败:", error);
    alert(error.message || "上传失败");
  } finally {
    uploading.value = false;
  }
};

// CSV 描述文件上传相关函数
const triggerCsvFileSelect = () => {
  csvFileInput.value?.click();
};

const handleCsvFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files[0]) {
    const file = target.files[0];
    if (file.name.endsWith('.csv')) {
      csvFile.value = file;
    } else {
      alert('请选择 CSV 格式的文件');
      target.value = '';
    }
  }
};

const removeCsvFile = () => {
  csvFile.value = null;
  if (csvFileInput.value) {
    csvFileInput.value.value = '';
  }
};

const uploadCsvFile = async () => {
  if (!selectedDataset.value || !csvFile.value) return;

  csvUploading.value = true;
  try {
    const response = await uploadDescriptionFile(
      selectedDataset.value.id!,
      csvFile.value
    );
    if (response.data.code === 200) {
      alert('描述文件上传成功！');
      csvFile.value = null;
      if (csvFileInput.value) {
        csvFileInput.value.value = '';
      }
      // 刷新数据集列表以更新状态
      await loadDatasets();
      // 更新选中的数据集信息
      const updated = datasets.value.find(
        (d) => d.id === selectedDataset.value?.id
      );
      if (updated) {
        selectedDataset.value = updated;
      }
    } else {
      alert('上传失败：' + response.data.message);
    }
  } catch (error: any) {
    console.error('上传描述文件失败:', error);
    alert(error.message || '上传失败');
  } finally {
    csvUploading.value = false;
  }
};

// 格式化文件大小
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
};

// 关闭对话框
const closeDialogs = () => {
  showCreateDialog.value = false;
  showEditDialog.value = false;
  formData.value = {
    dataset_name: "",
    case_count: 0,
    clinical_data_desc: "",
    text_data_desc: "",
    imaging_data_desc: "",
    pathology_data_desc: "",
    genomics_data_desc: "",
    annotation_desc: "",
    notes: "",
  };
  selectedDataset.value = null;
};

// 初始化
onMounted(() => {
  loadDatasets();
});
</script>

<style scoped>
.dataset-manage {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: #4f46e5;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: #4338ca;
}

.btn-primary:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

.btn-secondary {
  padding: 10px 20px;
  background: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-secondary:hover {
  background: #e5e7eb;
}

.btn-icon {
  padding: 6px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  color: #6b7280;
  transition: all 0.2s;
}

.btn-icon:hover {
  background: #f3f4f6;
  color: #374151;
}

.btn-icon.btn-danger:hover {
  background: #fef2f2;
  color: #dc2626;
}

.btn-link {
  background: none;
  border: none;
  color: #4f46e5;
  cursor: pointer;
  text-decoration: underline;
  font-size: inherit;
}

.dataset-list {
  display: grid;
  gap: 20px;
}

.dataset-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.dataset-card:hover {
  border-color: #4f46e5;
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.1);
}

.dataset-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.dataset-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  background: #eef2ff;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4f46e5;
}

.dataset-info {
  flex: 1;
  min-width: 0;
}

.dataset-name {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 4px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dataset-count {
  font-size: 14px;
  color: #6b7280;
  margin: 0 0 8px 0;
}

.dataset-status {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.2s;
}

.status-tag svg {
  flex-shrink: 0;
}

.status-success {
  background: #d1fae5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}

.status-warning {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
}

.dataset-actions {
  display: flex;
  gap: 4px;
}

/* 新的数据集卡片主体 */
.dataset-body {
  margin-top: 12px;
}

.data-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.data-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.data-tag.clinical {
  background: #eff6ff;
  color: #1e40af;
  border: 1px solid #bfdbfe;
}

.data-tag.text {
  background: #f0fdf4;
  color: #15803d;
  border: 1px solid #bbf7d0;
}

.data-tag.imaging {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
}

.data-tag.pathology {
  background: #fce7f3;
  color: #9f1239;
  border: 1px solid #fbcfe8;
}

.data-tag.genomics {
  background: #f3e8ff;
  color: #6b21a8;
  border: 1px solid #e9d5ff;
}

.data-tag.annotation {
  background: #ecfeff;
  color: #155e75;
  border: 1px solid #a5f3fc;
}

.dataset-notes {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 8px 12px;
  background: #f9fafb;
  border-radius: 6px;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.5;
}

/* 旧样式保留（如果还在使用） */
.dataset-descriptions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.desc-item {
  font-size: 13px;
  line-height: 1.5;
}

.desc-label {
  font-weight: 500;
  color: #6b7280;
  margin-right: 4px;
}

.desc-text {
  color: #374151;
}

.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: #9ca3af;
}

.empty-state svg {
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state p {
  font-size: 16px;
  margin-bottom: 20px;
}

.loading-state {
  text-align: center;
  padding: 80px 20px;
  color: #9ca3af;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #f3f4f6;
  border-top-color: #4f46e5;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Modal样式 */
.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-content {
  background: white;
  border-radius: 12px;
  width: 100%;
  max-width: 600px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-large {
  max-width: 800px;
}

.modal-header {
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.modal-header h2 {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.dataset-status-inline {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.btn-close {
  background: none;
  border: none;
  font-size: 28px;
  color: #9ca3af;
  cursor: pointer;
  line-height: 1;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;
}

.btn-close:hover {
  background: #f3f4f6;
  color: #374151;
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* 表单分组 */
.form-section {
  margin-bottom: 32px;
}

.form-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 16px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid #f3f4f6;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 16px;
  align-items: start;
}

.form-group {
  margin-bottom: 20px;
}

.form-group-small {
  width: 120px;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 8px;
}

.form-group label svg {
  margin-right: 4px;
}

.required {
  color: #dc2626;
}

.help-text {
  display: block;
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
  font-style: italic;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #4f46e5;
}

.form-group input:disabled {
  background: #f9fafb;
  color: #9ca3af;
  cursor: not-allowed;
}

/* 详情页面样式 */
.detail-section {
  margin-bottom: 32px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.section-title-detail {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 20px 0;
  padding-bottom: 12px;
  border-bottom: 2px solid #e5e7eb;
}

.section-title-detail svg {
  color: #4f46e5;
}

/* 统计卡片 */
.stats-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 56px;
  height: 56px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.stat-content {
  flex: 1;
}

.stat-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 4px;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: white;
}

/* 数据卡片网格 */
.data-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

/* 数据卡片样式 */
.data-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 16px;
  transition: all 0.2s;
}

.data-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.data-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.data-card-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.data-card-header h4 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}

.data-card-content {
  font-size: 14px;
  line-height: 1.6;
  color: #4b5563;
  margin: 0;
}

/* 不同数据类型的颜色 */
.data-card.clinical .data-card-icon {
  background: #eff6ff;
  color: #1e40af;
}

.data-card.clinical .data-card-header h4 {
  color: #1e40af;
}

.data-card.clinical {
  border-left: 3px solid #3b82f6;
}

.data-card.text .data-card-icon {
  background: #f0fdf4;
  color: #15803d;
}

.data-card.text .data-card-header h4 {
  color: #15803d;
}

.data-card.text {
  border-left: 3px solid #22c55e;
}

.data-card.imaging .data-card-icon {
  background: #fef3c7;
  color: #92400e;
}

.data-card.imaging .data-card-header h4 {
  color: #92400e;
}

.data-card.imaging {
  border-left: 3px solid #f59e0b;
}

.data-card.pathology .data-card-icon {
  background: #fce7f3;
  color: #9f1239;
}

.data-card.pathology .data-card-header h4 {
  color: #9f1239;
}

.data-card.pathology {
  border-left: 3px solid #e11d48;
}

.data-card.genomics .data-card-icon {
  background: #f3e8ff;
  color: #6b21a8;
}

.data-card.genomics .data-card-header h4 {
  color: #6b21a8;
}

.data-card.genomics {
  border-left: 3px solid #a855f7;
}

.data-card.annotation .data-card-icon {
  background: #ecfeff;
  color: #155e75;
}

.data-card.annotation .data-card-header h4 {
  color: #155e75;
}

.data-card.annotation {
  border-left: 3px solid #06b6d4;
}

.data-card.notes .data-card-icon {
  background: #fef9c3;
  color: #854d0e;
}

.data-card.notes .data-card-header h4 {
  color: #854d0e;
}

.data-card.notes {
  border-left: 3px solid #facc15;
}

/* 旧样式保留 */
.detail-section h3 {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 16px 0;
}

.detail-section h4 {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin: 0 0 12px 0;
}

.info-grid {
  display: grid;
  gap: 12px;
}

.info-item {
  display: flex;
  gap: 8px;
}

.info-label {
  font-weight: 500;
  color: #6b7280;
  min-width: 80px;
}

.info-value {
  color: #374151;
  flex: 1;
}

/* 上传区域 */
.upload-area {
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  padding: 40px 20px;
  text-align: center;
  transition: all 0.2s;
  cursor: pointer;
}

.upload-area:hover {
  border-color: #4f46e5;
  background: #fafbff;
}

.upload-area.drag-over {
  border-color: #4f46e5;
  background: #eef2ff;
}

.upload-icon {
  color: #9ca3af;
  margin-bottom: 12px;
}

.upload-text {
  font-size: 14px;
  color: #374151;
  margin: 0 0 4px 0;
}

.upload-hint {
  font-size: 12px;
  color: #9ca3af;
  margin: 0;
}

.file-list {
  margin-top: 20px;
  padding: 16px;
  background: #f9fafb;
  border-radius: 8px;
}

.file-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}

.file-list-header h4 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #374151;
}

.file-list-actions {
  display: flex;
  gap: 8px;
}

.file-list-container {
  max-height: 400px;
  overflow-y: auto;
  padding-right: 4px;
}

.file-list-container::-webkit-scrollbar {
  width: 8px;
}

.file-list-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.file-list-container::-webkit-scrollbar-thumb {
  background: #cbd5e0;
  border-radius: 4px;
}

.file-list-container::-webkit-scrollbar-thumb:hover {
  background: #a0aec0;
}

/* 文件夹分组样式 */
.folder-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.folder-group {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
}

.folder-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  cursor: pointer;
  transition: all 0.3s;
  user-select: none;
}

.folder-header:hover {
  background: linear-gradient(135deg, #5568d3 0%, #65408a 100%);
}

.folder-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  color: white;
}

.folder-icon {
  color: white;
  flex-shrink: 0;
}

.folder-name {
  font-weight: 600;
  font-size: 14px;
  color: white;
}

.folder-count {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
}

.expand-icon {
  color: white;
  transition: transform 0.3s;
  flex-shrink: 0;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.folder-files {
  background: #f9fafb;
}

.folder-files-container {
  max-height: 300px;
  overflow-y: auto;
  padding: 12px;
}

.folder-files-container::-webkit-scrollbar {
  width: 6px;
}

.folder-files-container::-webkit-scrollbar-track {
  background: #e5e7eb;
  border-radius: 3px;
}

.folder-files-container::-webkit-scrollbar-thumb {
  background: #9ca3af;
  border-radius: 3px;
}

.folder-files-container::-webkit-scrollbar-thumb:hover {
  background: #6b7280;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: white;
  border-radius: 6px;
  margin-bottom: 8px;
  transition: background-color 0.2s;
}

.file-item:hover {
  background: #f3f4f6;
}

.file-item:last-child {
  margin-bottom: 0;
}

.file-icon {
  color: #6b7280;
  flex-shrink: 0;
}

.file-name {
  flex: 1;
  font-size: 13px;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
}

.file-size {
  font-size: 12px;
  color: #9ca3af;
  min-width: 80px;
  text-align: right;
}

.upload-btn {
  width: 100%;
  margin-top: 12px;
}

/* 文件浏览器样式 */
.file-browser-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px 24px;
  border-bottom: none;
}

.file-browser-header .header-title-wrapper {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.file-browser-header .header-icon {
  width: 48px;
  height: 48px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(10px);
}

.file-browser-header .header-icon svg {
  color: white;
}

.file-browser-header .header-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-browser-header h2 {
  color: white;
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.file-browser-header .header-subtitle {
  color: rgba(255, 255, 255, 0.85);
  font-size: 13px;
  font-weight: 400;
}

.file-browser-header .btn-close {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  width: 36px;
  height: 36px;
  border-radius: 8px;
}

.file-browser-header .btn-close:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: scale(1.05);
}

.file-breadcrumb {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-radius: 12px;
  margin-bottom: 24px;
  border: 1px solid #bae6fd;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.file-breadcrumb svg {
  color: #0ea5e9;
  flex-shrink: 0;
}

.breadcrumb-path {
  flex: 1;
  font-size: 14px;
  color: #0c4a6e;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 6px;
  border: 1px solid rgba(14, 165, 233, 0.2);
}

.btn-back {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: white;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.btn-back:hover {
  background: #0ea5e9;
  border-color: #0ea5e9;
  color: white;
  box-shadow: 0 2px 4px rgba(14, 165, 233, 0.3);
  transform: translateX(-2px);
}

.btn-back:hover svg {
  transform: translateX(-2px);
}

.btn-back svg {
  width: 16px;
  height: 16px;
  transition: all 0.2s;
}

.files-loading {
  text-align: center;
  padding: 60px 20px;
  color: #9ca3af;
}

.empty-files {
  text-align: center;
  padding: 60px 20px;
  color: #9ca3af;
}

.empty-files svg {
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-files p {
  font-size: 14px;
  margin: 0;
}

/* 文件列表容器 */
.files-list-container {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
}

/* 表头 */
.files-list-header {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: linear-gradient(to bottom, #f9fafb, #f3f4f6);
  border-bottom: 2px solid #e5e7eb;
  font-weight: 600;
  font-size: 13px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.header-col {
  display: flex;
  align-items: center;
}

.col-name {
  flex: 1;
  min-width: 0;
}

.col-size {
  width: 120px;
  justify-content: flex-end;
}

.col-time {
  width: 160px;
  justify-content: flex-end;
}

/* 文件列表 */
.files-list {
  max-height: 500px;
  overflow-y: auto;
}

.file-list-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #f3f4f6;
  transition: all 0.2s;
  cursor: default;
}

.file-list-item:last-child {
  border-bottom: none;
}

.file-list-item:hover {
  background: #f9fafb;
}

.file-list-item.is-directory {
  cursor: pointer;
}

.file-list-item.is-directory:hover {
  background: linear-gradient(to right, #eff6ff, #f0f9ff);
  border-left: 3px solid #3b82f6;
  padding-left: 13px;
}

.file-list-item.is-directory:hover .icon-folder {
  color: #3b82f6;
  transform: scale(1.1);
}

.file-list-item.is-directory:hover .file-name-text {
  color: #2563eb;
  font-weight: 600;
}

.file-col {
  display: flex;
  align-items: center;
}

/* 文件图标包装器 */
.file-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  margin-right: 12px;
  transition: all 0.2s;
}

.icon-folder {
  color: #60a5fa;
  transition: all 0.2s;
}

.icon-file {
  color: #9ca3af;
}

/* 文件名 */
.file-name-text {
  font-size: 14px;
  color: #374151;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: all 0.2s;
}

/* 文件夹指示器 */
.folder-indicator {
  color: #d1d5db;
  font-size: 18px;
  font-weight: 300;
}

/* 文件大小和时间 */
.col-size,
.col-time {
  font-size: 13px;
  color: #6b7280;
}

.col-size {
  font-weight: 500;
}

.col-time {
  color: #9ca3af;
}

/* 滚动条样式 */
.files-list::-webkit-scrollbar {
  width: 8px;
}

.files-list::-webkit-scrollbar-track {
  background: #f9fafb;
}

.files-list::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 4px;
}

.files-list::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}

/* CSV 描述文件上传样式 */
.csv-upload-area {
  background: #f9fafb;
  border-radius: 12px;
  padding: 20px;
  margin-top: 12px;
}

.csv-info {
  margin-bottom: 16px;
  padding: 12px;
  background: #e0f2fe;
  border-left: 3px solid #0284c7;
  border-radius: 8px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #0c4a6e;
  font-size: 13px;
}

.info-item svg {
  flex-shrink: 0;
}

.csv-upload-content {
  margin-top: 12px;
}

.csv-description {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 16px;
  line-height: 1.6;
}

.csv-description code {
  background: #e5e7eb;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  color: #374151;
  font-size: 12px;
}

.csv-file-preview {
  margin-bottom: 16px;
  padding: 12px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.file-preview-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-preview-item svg {
  flex-shrink: 0;
  color: #10b981;
}

.file-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-info .file-name {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}

.file-info .file-size {
  font-size: 12px;
  color: #9ca3af;
}

.csv-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  background: #d1fae5;
  color: #065f46;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  margin-left: 8px;
}

.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  background: white;
  color: #374151;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: #f9fafb;
  border-color: #9ca3af;
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>

