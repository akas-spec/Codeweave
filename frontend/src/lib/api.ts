const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('token');
    }
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('token', token);
    }
  }

  logout() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
    }
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Health check
  async healthCheck() {
    return this.request('/health');
  }

  // Auth
  async getGithubLoginUrl() {
    return this.request<{ auth_url: string }>('/api/auth/github/login');
  }

  async githubCallback(code: string) {
    return this.request<{ access_token: string; token_type: string }>('/api/auth/github/callback', {
      method: 'POST',
      body: JSON.stringify({ code }),
    });
  }

  async getMe() {
    return this.request<any>('/api/auth/me');
  }

  // Repositories
  async connectRepo(githubUrl: string) {
    return this.request<{ id: number }>('/api/repos/connect', {
      method: 'POST',
      body: JSON.stringify({ github_url: githubUrl }),
    });
  }

  async listRepos() {
    return this.request('/api/repos');
  }

  async listGithubRepos() {
    return this.request('/api/repos/github');
  }

  async triggerIngestion(repoId: number) {
    return this.request(`/api/repos/${repoId}/ingest`, {
      method: 'POST',
    });
  }

  async getIngestionStatus(repoId: number) {
    return this.request(`/api/repos/${repoId}/status`);
  }

  // Chat
  async chat(question: string, repositoryId: number) {
    return this.request('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ question, repository_id: repositoryId }),
    });
  }
}

export const api = new ApiClient(API_URL);
export default api;
