/**
 * User & Authentication Types
 */

export type UserRole = 'admin' | 'project_admin' | 'operator';

export interface User {
  id: number;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  first_name?: string;
  last_name?: string | null;
  profile_image?: string | null;
}

export interface UserWithResourceCounts extends User {
  datasets_count: number;
  projects_count: number;
  prediction_jobs_count: number;
}

export interface UserCreateRequest {
  email: string;
  password: string;
  role: UserRole;
  first_name?: string;
  last_name?: string;
}

export interface UserUpdateRequest {
  email?: string;
  role?: UserRole;
  is_active?: boolean;
  password?: string;
  first_name?: string;
  last_name?: string;
}

export interface UsersListParams {
  skip?: number;
  limit?: number;
  role?: UserRole;
  is_active?: boolean;
  search?: string;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface ApiKey {
  id: number;
  user_id: number;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
}

export interface ApiKeyCreateResponse extends ApiKey {
  key: string;  // Full API key - only shown once on creation!
}

export interface ProfileUpdateRequest {
  first_name: string;
  last_name?: string | null;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface PasswordStrengthResponse {
  is_valid: boolean;
  message: string;
  strength_score: number;  // 0-4
  strength_label: string;  // "Very Weak", "Weak", "Medium", "Strong", "Very Strong"
}
