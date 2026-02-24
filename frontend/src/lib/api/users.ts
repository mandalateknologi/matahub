/**
 * User Management API
 * Admin-only endpoints for managing users
 */
import client from './client';
import type { User, UserWithResourceCounts, UserCreateRequest, UsersListParams, UserUpdateRequest } from '@/lib/types';



export const usersAPI = {
  /**
   * List all users with optional filters
   */
  async list(params?: UsersListParams): Promise<UserWithResourceCounts[]> {
    const response = await client.get<UserWithResourceCounts[]>('/users', { params });
    return response.data;
  },

  /**
   * Get user by ID with resource counts
   */
  async get(userId: number): Promise<UserWithResourceCounts> {
    const response = await client.get<UserWithResourceCounts>(`/users/${userId}`);
    return response.data;
  },

  /**
   * Create a new user
   */
  async create(data: UserCreateRequest): Promise<User> {
    const response = await client.post<User>('/users', data);
    return response.data;
  },

  /**
   * Update user details
   */
  async update(userId: number, data: UserUpdateRequest): Promise<User> {
    const response = await client.put<User>(`/users/${userId}`, data);
    return response.data;
  },

  /**
   * Delete user (soft delete by default, hard delete with force=true)
   */
  async delete(userId: number, force: boolean = false): Promise<void> {
    await client.delete(`/users/${userId}`, { params: { force } });
  },

  /**
   * Reactivate a soft-deleted user
   */
  async reactivate(userId: number): Promise<User> {
    const response = await client.post<User>(`/users/${userId}/reactivate`);
    return response.data;
  },
};
