/**
 * API Keys Management API
 * Endpoints for managing user API keys
 */
import client from './client';
import type { ApiKey, ApiKeyCreateResponse } from '@/lib/types';

export const apiKeysAPI = {
  /**
   * Generate a new API key for the current user
   * 
   * **Important:** 
   * - Each user can only have ONE API key
   * - The full key is only shown once - store it securely!
   * - If a key already exists, revoke it first
   * 
   * @throws {409} If user already has an API key
   */
  async generate(): Promise<ApiKeyCreateResponse> {
    const response = await client.post<ApiKeyCreateResponse>('/api-keys');
    return response.data;
  },

  /**
   * Get metadata about the current user's API key
   * 
   * **Note:** This returns only metadata (prefix, dates).
   * The full API key is never retrievable after creation.
   * 
   * @throws {404} If no API key exists
   */
  async getCurrent(): Promise<ApiKey> {
    const response = await client.get<ApiKey>('/api-keys/current');
    return response.data;
  },

  /**
   * Revoke (delete) the current user's API key
   * 
   * This action is immediate and irreversible.
   * Any applications using this key will be unable to authenticate.
   * 
   * @throws {404} If no API key exists
   */
  async revoke(): Promise<void> {
    await client.delete('/api-keys/current');
  }
};
