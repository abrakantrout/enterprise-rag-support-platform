import axios from 'axios';

// Get backend API URL from Vite env or default to localhost
const BASE_URL = import.meta.env.VITE_BACKEND_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to automatically inject access tokens from local storage
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// --- TYPE DEFINITIONS ---

export interface UserProfile {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  organization_id: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token: string;
}

export interface DocumentPipelineStatus {
  extracted: boolean;
  chunked: boolean;
  embedded: boolean;
  indexed: boolean;
}

export interface DocumentMetadata {
  id: string;
  filename: string;
  stored_path: string;
  file_type: string;
  file_size: number;
  status: string; // "Processing" | "Completed" | "Failed"
  visibility: string;
  category?: string;
  uploader_id: string;
  organization_id: string;
  extracted_at?: string;
  created_at: string;
  updated_at: string;
  pipeline?: DocumentPipelineStatus;
}

export interface DocumentListResponse {
  items: DocumentMetadata[];
  pagination: {
    total_items: number;
    page_size: number;
    current_page: number;
    total_pages: number;
  };
}

export interface OverviewTelemetry {
  total_documents: number;
  processed_documents: number;
  failed_documents: number;
  total_chunks: number;
  total_chat_sessions: number;
  total_messages: number;
  total_feedback: number;
  thumbs_up_count: number;
  thumbs_down_count: number;
}

export interface RecentQuestion {
  message_id: string;
  session_id: string;
  content: string;
  created_at: string;
}

export interface LowRatedAnswer {
  feedback_id: string;
  message_id: string;
  session_id: string;
  answer: string;
  comment?: string;
  score: number;
  rating: string;
  created_at: string;
}

export interface ChatSession {
  session_id: string;
  created_at: string;
  title?: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations?: Array<{
    source_label: string;
    document_name: string;
    page_number?: number;
    similarity_score: number;
    text_preview: string;
  }>;
  verification?: {
    verification_status: 'verified' | 'unverified' | 'failed';
    confidence: number;
    reason: string;
  };
  created_at: string;
}

export interface ChatSessionDetail {
  session_id: string;
  messages: ChatMessage[];
}

export interface AnswerResponse {
  message_id: string;
  content: string;
  citations?: ChatMessage['citations'];
  verification?: ChatMessage['verification'];
}

// --- API METHODS ---

export const api = {
  // Health
  checkHealth: async (): Promise<boolean> => {
    try {
      const res = await axios.get(`${BASE_URL}/health`, { timeout: 3000 });
      return res.status === 200;
    } catch {
      return false;
    }
  },

  // Auth
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const params = new URLSearchParams();
    params.append('username', email);
    params.append('password', password);
    const res = await apiClient.post<TokenResponse>('/api/v1/auth/login', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return res.data;
  },

  getMe: async (): Promise<UserProfile> => {
    const res = await apiClient.get<UserProfile>('/api/v1/auth/me');
    return res.data;
  },

  // Analytics
  getOverview: async (): Promise<OverviewTelemetry> => {
    const res = await apiClient.get<OverviewTelemetry>('/api/v1/analytics/overview');
    return res.data;
  },

  getRecentQuestions: async (limit = 10): Promise<RecentQuestion[]> => {
    const res = await apiClient.get<RecentQuestion[]>(`/api/v1/analytics/recent-questions?limit=${limit}`);
    return res.data;
  },

  getLowRatedAnswers: async (limit = 10): Promise<LowRatedAnswer[]> => {
    const res = await apiClient.get<LowRatedAnswer[]>(`/api/v1/analytics/low-rated-answers?limit=${limit}`);
    return res.data;
  },

  getDocumentStatusCounts: async (): Promise<Record<string, number>> => {
    const res = await apiClient.get<Record<string, number>>('/api/v1/analytics/document-status');
    return res.data;
  },

  // Documents
  listDocuments: async (page = 1, size = 50, status?: string): Promise<DocumentListResponse> => {
    const url = `/api/v1/documents?page=${page}&size=${size}${status ? `&status=${status}` : ''}`;
    const res = await apiClient.get<DocumentListResponse>(url);
    return res.data;
  },

  uploadDocument: async (file: File, category?: string, visibility = 'public'): Promise<DocumentMetadata> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('visibility', visibility);
    if (category) {
      formData.append('category', category);
    }
    const res = await apiClient.post<DocumentMetadata>('/api/v1/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  deleteDocument: async (documentId: string): Promise<{ message: string }> => {
    const res = await apiClient.delete<{ message: string }>(`/api/v1/documents/${documentId}`);
    return res.data;
  },

  runExtraction: async (documentId: string): Promise<any> => {
    const res = await apiClient.post(`/api/v1/documents/${documentId}/extract`);
    return res.data;
  },

  runChunking: async (documentId: string): Promise<any> => {
    const res = await apiClient.post(`/api/v1/documents/${documentId}/chunks`);
    return res.data;
  },

  runEmbeddings: async (documentId: string): Promise<any> => {
    const res = await apiClient.post(`/api/v1/documents/${documentId}/embeddings`);
    return res.data;
  },

  runIndexing: async (documentId: string): Promise<any> => {
    const res = await apiClient.post(`/api/v1/documents/${documentId}/index`);
    return res.data;
  },

  // Chat
  createChatSession: async (): Promise<ChatSession> => {
    const res = await apiClient.post<ChatSession>('/api/v1/chat/sessions');
    return res.data;
  },

  listChatSessions: async (): Promise<ChatSession[]> => {
    const res = await apiClient.get<ChatSession[]>('/api/v1/chat/sessions');
    return res.data;
  },

  getChatSession: async (sessionId: string): Promise<ChatSessionDetail> => {
    const res = await apiClient.get<ChatSessionDetail>(`/api/v1/chat/sessions/${sessionId}`);
    return res.data;
  },

  deleteChatSession: async (sessionId: string): Promise<{ message: string }> => {
    const res = await apiClient.delete<{ message: string }>(`/api/v1/chat/sessions/${sessionId}`);
    return res.data;
  },

  askQuestion: async (sessionId: string, question: string): Promise<AnswerResponse> => {
    const res = await apiClient.post<AnswerResponse>(`/api/v1/chat/sessions/${sessionId}/answer`, { question });
    return res.data;
  },

  // Feedback
  submitFeedback: async (messageId: string, rating: 'thumbs_up' | 'thumbs_down', comment?: string): Promise<any> => {
    const payload: { message_id: string; rating: string; comment?: string } = {
      message_id: messageId,
      rating,
    };
    if (comment) {
      payload.comment = comment;
    }
    const res = await apiClient.post('/api/v1/feedback', payload);
    return res.data;
  },
};
