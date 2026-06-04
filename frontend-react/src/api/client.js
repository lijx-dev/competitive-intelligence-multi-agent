// ★ 使用 Vite 代理，所有请求走相对路径，彻底消除 CORS
const API_BASE_URL = '';

export const TOKEN_KEY = 'ci_agent_token';
export const USER_KEY = 'ci_agent_user';
export const ANALYSIS_RECORDS_UPDATED_EVENT = 'ci:analysis-records-updated';

function storage() {
  return typeof window === 'undefined' ? null : window.localStorage;
}

export function getStoredToken() {
  return storage()?.getItem(TOKEN_KEY) || '';
}

export function getStoredUser() {
  const raw = storage()?.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function saveAuth(token, user) {
  storage()?.setItem(TOKEN_KEY, token);
  storage()?.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  storage()?.removeItem(TOKEN_KEY);
  storage()?.removeItem(USER_KEY);
}

/**
 * ★ 免登录一键演示：自动注入伪造 token，跳过注册/登录
 */
export function autoDemoAuth() {
  const demoToken = 'demo_token_ci_agent_2026';
  const demoUser = { name: '演示用户', email: 'demo@ci-agent.local', role: '分析师' };
  saveAuth(demoToken, demoUser);
  return { token: demoToken, user: demoUser };
}

export function notifyAnalysisRecordsUpdated(detail = {}) {
  const payload = { ...detail, updatedAt: Date.now() };
  storage()?.setItem('ci_analysis_records_updated_at', String(payload.updatedAt));
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(ANALYSIS_RECORDS_UPDATED_EVENT, { detail: payload }));
  }
}

async function readBody(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function extractError(payload, status) {
  if (!payload) return `请求失败，状态码 ${status}`;
  if (typeof payload === 'string') return payload;
  if (typeof payload.detail === 'string') return payload.detail;
  if (Array.isArray(payload.detail)) return payload.detail.map((item) => item.msg || item.message || item).join('；');
  if (payload.message) return payload.message;
  return `请求失败，状态码 ${status}`;
}

async function request(path, options = {}) {
  const token = options.token ?? getStoredToken();
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  const payload = await readBody(response);

  if (!response.ok) {
    throw new Error(extractError(payload, response.status));
  }

  return payload;
}

/**
 * SSE 流式分析 — 连接 POST /analyze/stream，逐节点回调。
 *
 * @param {{ competitor: string, urls: string[] }} payload
 * @param {{ onEvent(nodeId, data), onError(err), onComplete(data) }} callbacks
 * @returns {AbortController} 可调用 .abort() 取消
 */
export function analyzeStream(payload, callbacks) {
  const controller = new AbortController();
  const token = getStoredToken();

  fetch(`${API_BASE_URL}/analyze/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const body = await readBody(response);
        throw new Error(extractError(body, response.status));
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let terminalReceived = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        buffer = buffer.replace(/\r\n/g, '\n');

        const frames = buffer.split('\n\n');
        buffer = frames.pop();

        for (const frame of frames) {
          if (!frame.trim()) continue;
          let eventName = '';
          let dataStr = '';
          for (const line of frame.split('\n')) {
            if (line.startsWith('event:')) eventName = line.slice(6).trim();
            else if (line.startsWith('data:')) dataStr = line.slice(5).trim();
          }
          if (!eventName || !dataStr) continue;
          try {
            const data = JSON.parse(dataStr);
            if (eventName === 'error') {
              terminalReceived = true;
              callbacks.onError?.(data.error || '分析过程出错');
            } else if (eventName === 'complete') {
              terminalReceived = true;
              callbacks.onComplete?.(data);
            } else {
              callbacks.onEvent?.(eventName, data);
            }
          } catch {
            /* 非 JSON 数据行，跳过 */
          }
        }
      }
      /* 流正常结束（生产模式无 complete 事件） */
      if (!terminalReceived) callbacks.onComplete?.(null);
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        callbacks.onError?.(err.message || '流式分析连接失败');
      }
    });

  return controller;
}

export const api = {
  baseUrl: API_BASE_URL || '/',

  // ★ 注册/登录已废弃（免登录模式），保留兼容但不调用后端
  register: () => Promise.resolve(autoDemoAuth()),
  login: () => Promise.resolve(autoDemoAuth()),
  me: () => Promise.resolve({ user: getStoredUser() }),

  health: () => request('/health'),
  systemInfo: () => request('/api/system-info'),
  mockStatus: () => request('/api/v1/mock/status'),
  mockToggle: (enabled, scenario = 'scenario1') =>
    request('/api/v1/mock/toggle', {
      method: 'POST',
      body: JSON.stringify({ enabled, scenario }),
    }),
  competitors: () => request('/competitors/all'),
  createCompetitor: (payload) =>
    request('/competitors', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateCompetitor: (id, payload) =>
    request(`/competitors/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  analyze: (payload) =>
    request('/analyze', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  analysisRecords: () => request('/analysis/records'),

  config: () => request('/api/config'),
  ourProduct: () => request('/api/our-product'),
  updateOurProduct: (payload) =>
    request('/api/our-product', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  feishuTest: () => request('/api/v1/feishu/test', { method: 'POST' }),
  feishuFeedback: () => request('/api/v1/feishu/feedback'),
  submitFeishuFeedback: (payload) =>
    request('/api/v1/feishu/feedback', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  infraStatus: () => request('/api/v1/infra/status'),
  decisionLogs: (limit = 20) => request(`/api/v1/infra/decision-logs?limit=${limit}`),
  decisionLogsTimeline: () => request('/api/v1/infra/decision-logs/timeline'),
  tokenUsage: () => request('/api/v1/infra/token-usage'),
  tokenQuota: () => request('/api/v1/infra/token-quota'),
  infraEvents: (limit = 200) => request(`/api/v1/infra/events?limit=${limit}`),
  eventTrace: (eventId) => request(`/api/v1/infra/events/${eventId}/trace`),
  dagSnapshot: () => request('/api/v1/infra/dag-snapshot'),
  auditLogs: (limit = 50) => request(`/api/v1/infra/audit-logs?limit=${limit}`),
  anomalies: () => request('/api/v1/infra/anomalies'),

  evolutionStats: () => request('/api/v1/evolution/stats'),
  evolutionSnapshots: (limit = 20) => request(`/api/v1/evolution/snapshots?limit=${limit}`),
  evolutionTemplates: () => request('/api/v1/evolution/templates'),

  ragStats: () => request('/api/v1/rag/stats'),
  ragQuery: (query, k = 5) =>
    request(`/api/v1/rag/query?query=${encodeURIComponent(query)}&k=${k}`, {
      method: 'POST',
    }),
  ragIngest: () => request('/api/v1/rag/ingest', { method: 'POST' }),

  analysisRecord: (id) => request(`/analysis/records/${id}`),
  deleteCompetitor: (id) => request(`/competitors/${id}`, { method: 'DELETE' }),

  updateConfig: (payload) =>
    request('/api/config', { method: 'PUT', body: JSON.stringify(payload) }),

  // ── 飞书CLI全局总调度官 ──
  fetchJson: (path, options) => request(path, options),
  feishuCommand: (text, mode = 'mock') =>
    request('/api/v1/feishu/command', {
      method: 'POST',
      body: JSON.stringify({ text, mode }),
    }),
  feishuTaskStatus: (taskId) => request(`/api/v1/feishu/task-status/${taskId}`),
  feishuSchedulerTasks: () => request('/api/v1/feishu/scheduler/tasks'),
  feishuSchedulerStats: () => request('/api/v1/feishu/scheduler/stats'),
  feishuSchedulerTest: () => request('/api/v1/feishu/scheduler/test', { method: 'POST' }),
};
