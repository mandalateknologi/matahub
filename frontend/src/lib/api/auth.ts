/**
 * Authentication API
 */
import client, { apiClient } from './client';
import type { LoginCredentials, Token, User } from '@/lib/types';

export const authAPI = {
  async login(credentials: LoginCredentials): Promise<Token> {
    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    const response = await client.post<Token>('/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    // Store token
    apiClient.setToken(response.data.access_token);
    return response.data;
  },

  async getCurrentUser(): Promise<User> {
    const response = await client.get<User>('/auth/me');
    return response.data;
  },

  logout(): void {
    apiClient.clearToken();
  },

  isAuthenticated(): boolean {
    return apiClient.isAuthenticated();
  },
};
