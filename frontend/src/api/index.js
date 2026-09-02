import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response interceptor
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

// ─── Project API ──────────────────────────────────────────
export const projectApi = {
  list: () => api.get('/projects'),
  get: (id) => api.get(`/projects/${id}`),
  create: (data) => api.post('/projects', data),
  update: (id, data) => api.put(`/projects/${id}`, data),
  delete: (id) => api.delete(`/projects/${id}`),
}

// ─── Image API ────────────────────────────────────────────
export const imageApi = {
  list: (projectId, split) => api.get(`/projects/${projectId}/images`, { params: { split } }),
  upload: (projectId, files, split = 'train') => {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    formData.append('split', split)
    return api.post(`/projects/${projectId}/images/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  delete: (imageId) => api.delete(`/images/${imageId}`),
  updateSplit: (imageIds, split) => api.put('/images/split', { image_ids: imageIds, split }),
  autoSplit: (projectId) => api.post(`/projects/${projectId}/auto-split`),
}

// ─── Annotation API ───────────────────────────────────────
export const annotationApi = {
  list: (imageId) => api.get(`/images/${imageId}/annotations`),
  create: (data) => api.post(`/images/${data.image_id}/annotations`, data),
  update: (id, data) => api.put(`/annotations/${id}`, data),
  delete: (id) => api.delete(`/annotations/${id}`),
  clearAll: (imageId) => api.delete(`/images/${imageId}/annotations/all`),
  summary: (projectId) => api.get(`/projects/${projectId}/annotations/summary`),
}

// ─── Training API ─────────────────────────────────────────
export const trainApi = {
  listRuns: (projectId) => api.get(`/projects/${projectId}/runs`),
  getRun: (runId) => api.get(`/runs/${runId}`),
  start: (projectId, config) => api.post(`/projects/${projectId}/train`, config),
  cancel: (runId) => api.post(`/runs/${runId}/cancel`),
  listModels: () => api.get('/models/available'),
  downloadModel: (modelId) => api.post(`/models/download/${modelId}`),
  downloadStatus: (modelId) => api.get(`/models/download-status/${modelId}`),
  downloadPt: (projectId, runId) => api.get(`/projects/${projectId}/runs/${runId}/download`, { responseType: 'blob' }),
  exportModel: (projectId, runId, format) => api.post(`/projects/${projectId}/runs/${runId}/export`, null, { params: { format } }),
  getMetrics: (runId) => api.get(`/runs/${runId}/metrics`),
}

// ─── Inference API ────────────────────────────────────────
export const inferenceApi = {
  predict: (file, options = {}) => {
    const formData = new FormData()
    formData.append('file', file)
    if (options.runId) formData.append('run_id', options.runId)
    if (options.modelName) formData.append('model_name', options.modelName)
    if (options.confThreshold !== undefined) formData.append('conf_threshold', options.confThreshold)
    if (options.iouThreshold !== undefined) formData.append('iou_threshold', options.iouThreshold)
    
    return api.post('/predict', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

// ─── AI Annotation API ───────────────────────────────────
export const aiApi = {
  annotate: (projectId, data) => api.post(`/projects/${projectId}/ai-annotate`, null, { params: data }),
  smartSelect: (projectId, data) => api.post(`/projects/${projectId}/smart-select`, data),
  clear: (projectId, imageId) => api.post(`/projects/${projectId}/ai-clear`, null, { params: { image_id: imageId } }),
  // SAM 模型管理
  samStatus: () => api.get('/sam/status'),
  samDownload: () => api.post('/sam/download'),
  samDownloadStatus: () => api.get('/sam/download-status'),
}

export default api
