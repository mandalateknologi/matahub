/**
 * Profile API Client
 * Handles user profile management (self-service)
 */
import apiClient from "./client";
import type {
  User,
  ProfileUpdateRequest,
  ChangePasswordRequest,
  PasswordStrengthResponse,
} from "@/lib/types";

export const profileAPI = {
  /**
   * Get current user's profile
   */
  async getProfile(): Promise<User> {
    const { data } = await apiClient.get<User>("/profile/me");
    return data;
  },

  /**
   * Update current user's profile (first name, last name)
   */
  async updateProfile(profileData: ProfileUpdateRequest): Promise<User> {
    const { data } = await apiClient.patch<User>("/profile/me", profileData);
    return data;
  },

  /**
   * Change current user's password
   */
  async changePassword(
    passwordData: ChangePasswordRequest
  ): Promise<{ message: string }> {
    const { data } = await apiClient.post("/profile/change-password", passwordData);
    return data;
  },

  /**
   * Check password strength without saving
   */
  async checkPasswordStrength(password: string): Promise<PasswordStrengthResponse> {
    const { data } = await apiClient.post<PasswordStrengthResponse>(
      "/profile/password-strength",
      null,
      {
        params: { password },
      }
    );
    return data;
  },

  /**
   * Upload profile image
   */
  async uploadProfileImage(file: File): Promise<User> {
    const formData = new FormData();
    formData.append("file", file);

    const { data } = await apiClient.post<User>("/profile/upload-image", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return data;
  },

  /**
   * Delete profile image
   */
  async deleteProfileImage(): Promise<{ message: string }> {
    const { data} = await apiClient.delete("/profile/image");
    return data;
  },

  /**
   * Get profile image URL
   */
  getProfileImageUrl(user: User): string | null {
    if (!user.profile_image) return null;
    // Construct full URL from relative path
    return `/api/data/${user.profile_image}`;
  },
};
