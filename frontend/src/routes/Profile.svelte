<script lang="ts">
  import { onMount } from "svelte";
  import { authStore } from "../lib/stores/authStore";
  import { uiStore } from "../lib/stores/uiStore";
  import { profileAPI } from "../lib/api/profile";
  import PasswordStrengthIndicator from "../lib/components/shared/PasswordStrengthIndicator.svelte";
  import type { User, ProfileUpdateRequest, ChangePasswordRequest } from "@/lib/types";

  let user = $state<User | null>(null);
  let loading = $state(true);
  
  // Profile form
  let firstName = $state("");
  let lastName = $state("");
  let profileEditing = $state(false);
  let profileSaving = $state(false);
  
  // Password form
  let currentPassword = $state("");
  let newPassword = $state("");
  let confirmPassword = $state("");
  let passwordChanging = $state(false);
  
  // Image upload
  let uploadingImage = $state(false);
  let imagePreview = $state<string | null>(null);

  onMount(async () => {
    try {
      user = $authStore.user;
      if (user) {
        firstName = user.first_name || "";
        lastName = user.last_name || "";
        imagePreview = user.profile_image ? profileAPI.getProfileImageUrl(user) : null;
      }
    } catch (error: any) {
      console.error("Error loading profile:", error);
      uiStore.showToast("Failed to load profile", "error");
    } finally {
      loading = false;
    }
  });

  async function handleSaveProfile(e: Event) {
    e.preventDefault();
    if (!firstName.trim()) {
      uiStore.showToast("First name is required", "error");
      return;
    }

    try {
      profileSaving = true;
      const profileData: ProfileUpdateRequest = {
        first_name: firstName.trim(),
        last_name: lastName.trim() || null,
      };

      const updatedUser = await profileAPI.updateProfile(profileData);
      user = updatedUser;
      
      // Update auth store
      await authStore.checkAuth();
      
      uiStore.showToast("Profile updated successfully!", "success");
      profileEditing = false;
    } catch (error: any) {
      console.error("Error updating profile:", error);
      uiStore.showToast(
        error.response?.data?.detail || "Failed to update profile",
        "error"
      );
    } finally {
      profileSaving = false;
    }
  }

  async function handleChangePassword(e: Event) {
    e.preventDefault();
    if (!currentPassword || !newPassword) {
      uiStore.showToast("Please fill in all password fields", "error");
      return;
    }

    if (newPassword !== confirmPassword) {
      uiStore.showToast("New passwords do not match", "error");
      return;
    }

    if (newPassword.length < 8) {
      uiStore.showToast("Password must be at least 8 characters", "error");
      return;
    }

    try {
      passwordChanging = true;
      const passwordData: ChangePasswordRequest = {
        current_password: currentPassword,
        new_password: newPassword,
      };

      await profileAPI.changePassword(passwordData);
      
      uiStore.showToast("Password changed successfully!", "success");
      
      // Clear form
      currentPassword = "";
      newPassword = "";
      confirmPassword = "";
    } catch (error: any) {
      console.error("Error changing password:", error);
      uiStore.showToast(
        error.response?.data?.detail || "Failed to change password",
        "error"
      );
    } finally {
      passwordChanging = false;
    }
  }

  async function handleImageUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    
    if (!file) return;

    // Validate file size (5MB max)
    if (file.size > 5 * 1024 * 1024) {
      uiStore.showToast("Image must be less than 5MB", "error");
      return;
    }

    // Validate file type
    if (!file.type.startsWith("image/")) {
      uiStore.showToast("Please select an image file", "error");
      return;
    }

    try {
      uploadingImage = true;
      const updatedUser = await profileAPI.uploadProfileImage(file);
      user = updatedUser;
      imagePreview = profileAPI.getProfileImageUrl(updatedUser);
      
      // Update auth store
      await authStore.checkAuth();
      
      uiStore.showToast("Profile image uploaded successfully!", "success");
    } catch (error: any) {
      console.error("Error uploading image:", error);
      uiStore.showToast(
        error.response?.data?.detail || "Failed to upload image",
        "error"
      );
    } finally {
      uploadingImage = false;
      input.value = ""; // Reset input
    }
  }

  async function handleDeleteImage() {
    if (!confirm("Are you sure you want to delete your profile image?")) {
      return;
    }

    try {
      await profileAPI.deleteProfileImage();
      user = { ...user!, profile_image: null };
      imagePreview = null;
      
      // Update auth store
      await authStore.checkAuth();
      
      uiStore.showToast("Profile image deleted", "success");
    } catch (error: any) {
      console.error("Error deleting image:", error);
      uiStore.showToast(
        error.response?.data?.detail || "Failed to delete image",
        "error"
      );
    }
  }

  function getUserInitials(email: string): string {
    return email.substring(0, 2).toUpperCase();
  }

  function getRoleBadge(role: string): string {
    switch (role) {
      case "admin":
        return "👑 Admin";
      case "project_admin":
        return "📊 Project Admin";
      case "operator":
        return "🎯 Operator";
      default:
        return role;
    }
  }
</script>

<div class="profile-container">
  <div class="profile-header">
    <h1>Profile Settings</h1>
  </div>

  {#if loading}
    <div class="loading">Loading profile...</div>
  {:else if user}
    <!-- Profile Image Section -->
    <section class="profile-section">
      <h2>Profile Image</h2>
      <div class="image-section">
        <div class="avatar-container">
          {#if imagePreview}
            <img src={imagePreview} alt="Profile" class="avatar-image" />
          {:else}
            <div class="avatar-placeholder">
              {getUserInitials(user.email)}
            </div>
          {/if}
          
          {#if uploadingImage}
            <div class="avatar-overlay">Uploading...</div>
          {/if}
        </div>

        <div class="image-actions">
          <label class="btn btn-primary">
            <input
              type="file"
              accept="image/*"
              onchange={handleImageUpload}
              disabled={uploadingImage}
              style="display: none"
            />
            {uploadingImage ? "Uploading..." : "Upload Image"}
          </label>
          
          {#if user.profile_image}
            <button class="btn btn-danger" onclick={handleDeleteImage}>
              Delete Image
            </button>
          {/if}
          
          <p class="help-text">Max size: 5MB. Will be resized to 200x200px.</p>
        </div>
      </div>
    </section>

    <!-- Profile Info Section -->
    <section class="profile-section">
      <h2>Profile Information</h2>
      
      <div class="profile-info">
        <div class="info-row">
          <label>Email:</label>
          <span>{user.email}</span>
        </div>
        
        <div class="info-row">
          <label>Role:</label>
          <span>{getRoleBadge(user.role)}</span>
        </div>
      </div>

      <form class="profile-form" onsubmit={handleSaveProfile}>
        <div class="form-group">
          <label for="firstName">
            First Name <span class="required">*</span>
          </label>
          <input
            id="firstName"
            type="text"
            bind:value={firstName}
            placeholder="Enter your first name"
            maxlength="100"
            disabled={!profileEditing || profileSaving}
            required
          />
          <small>{firstName.length}/100</small>
        </div>

        <div class="form-group">
          <label for="lastName">Last Name</label>
          <input
            id="lastName"
            type="text"
            bind:value={lastName}
            placeholder="Enter your last name (optional)"
            maxlength="100"
            disabled={!profileEditing || profileSaving}
          />
          <small>{lastName.length}/100</small>
        </div>

        <div class="form-actions">
          {#if !profileEditing}
            <button
              type="button"
              class="btn btn-primary"
              onclick={() => (profileEditing = true)}
            >
              Edit Profile
            </button>
          {:else}
            <button
              type="submit"
              class="btn btn-primary"
              disabled={profileSaving}
            >
              {profileSaving ? "Saving..." : "Save Changes"}
            </button>
            <button
              type="button"
              class="btn btn-secondary"
              onclick={() => {
                profileEditing = false;
                firstName = user?.first_name || "";
                lastName = user?.last_name || "";
              }}
              disabled={profileSaving}
            >
              Cancel
            </button>
          {/if}
        </div>
      </form>
    </section>

    <!-- Change Password Section -->
    <section class="profile-section">
      <h2>Change Password</h2>
      
      <form class="password-form" onsubmit={handleChangePassword}>
        <div class="form-group">
          <label for="currentPassword">Current Password</label>
          <input
            id="currentPassword"
            type="password"
            bind:value={currentPassword}
            placeholder="Enter current password"
            disabled={passwordChanging}
            required
          />
        </div>

        <div class="form-group">
          <label for="newPassword">New Password</label>
          <input
            id="newPassword"
            type="password"
            bind:value={newPassword}
            placeholder="Enter new password (min 8 chars)"
            disabled={passwordChanging}
            required
          />
          <PasswordStrengthIndicator password={newPassword} />
        </div>

        <div class="form-group">
          <label for="confirmPassword">Confirm New Password</label>
          <input
            id="confirmPassword"
            type="password"
            bind:value={confirmPassword}
            placeholder="Confirm new password"
            disabled={passwordChanging}
            required
          />
          {#if confirmPassword && newPassword !== confirmPassword}
            <small class="error">Passwords do not match</small>
          {/if}
        </div>

        <div class="password-requirements">
          <p><strong>Password Requirements:</strong></p>
          <ul>
            <li>Minimum 8 characters</li>
            <li>At least one uppercase letter</li>
            <li>At least one lowercase letter</li>
            <li>At least one number</li>
          </ul>
        </div>

        <button
          type="submit"
          class="btn btn-primary"
          disabled={passwordChanging || newPassword !== confirmPassword}
        >
          {passwordChanging ? "Changing..." : "Change Password"}
        </button>
      </form>
    </section>
  {/if}
</div>

<style>
  .profile-container {
    padding: var(--spacing-xl);
    max-width: 800px;
    margin: 0 auto;
  }

  .profile-header {
    margin-bottom: var(--spacing-xl);
  }

  .profile-header h1 {
    color: var(--color-navy);
    margin: 0;
  }

  .profile-section {
    background: var(--color-bg-card);
    border-radius: var(--radius-lg);
    padding: var(--spacing-xl);
    box-shadow: var(--shadow-md);
    margin-bottom: var(--spacing-lg);
  }

  .profile-section h2 {
    color: var(--color-navy);
    margin-bottom: var(--spacing-md);
    font-size: var(--font-size-xl);
  }

  /* Image Section */
  .image-section {
    display: flex;
    gap: var(--spacing-xl);
    align-items: flex-start;
  }

  .avatar-container {
    position: relative;
    flex-shrink: 0;
  }

  .avatar-image,
  .avatar-placeholder {
    width: 150px;
    height: 150px;
    border-radius: 50%;
    object-fit: cover;
  }

  .avatar-placeholder {
    background: linear-gradient(135deg, var(--color-accent), #ff8a75);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--font-size-3xl);
    font-weight: 600;
  }

  .avatar-overlay {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    font-size: var(--font-size-sm);
  }

  .image-actions {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
  }

  .help-text {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
    margin: 0;
  }

  /* Profile Info */
  .profile-info {
    margin-bottom: var(--spacing-lg);
  }

  .info-row {
    display: flex;
    gap: var(--spacing-md);
    padding: var(--spacing-sm) 0;
    border-bottom: 1px solid var(--color-border-light);
  }

  .info-row label {
    font-weight: 600;
    color: var(--color-navy);
    min-width: 100px;
  }

  /* Forms */
  .profile-form,
  .password-form {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-lg);
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .form-group label {
    font-weight: 600;
    color: var(--color-navy);
    font-size: var(--font-size-sm);
  }

  .required {
    color: var(--color-error);
  }

  .form-group input {
    padding: var(--spacing-sm) var(--spacing-md);
    border: 2px solid var(--color-border);
    border-radius: var(--radius-md);
    font-size: var(--font-size-base);
  }

  .form-group input:focus {
    border-color: var(--color-accent);
    outline: none;
  }

  .form-group small {
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
  }

  .form-group small.error {
    color: var(--color-error);
  }

  .form-actions {
    display: flex;
    gap: var(--spacing-md);
  }

  /* Password Requirements */
  .password-requirements {
    background: var(--color-bg-light1);
    padding: var(--spacing-md);
    border-radius: var(--radius-md);
  }

  .password-requirements p {
    margin: 0 0 var(--spacing-sm) 0;
    font-size: var(--font-size-sm);
    color: var(--color-navy);
  }

  .password-requirements ul {
    margin: 0;
    padding-left: var(--spacing-lg);
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .password-requirements li {
    margin: var(--spacing-xs) 0;
  }

  /* Buttons */
  .btn {
    padding: var(--spacing-sm) var(--spacing-lg);
    border: none;
    border-radius: var(--radius-md);
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition-fast);
    font-size: var(--font-size-base);
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-primary {
    background: var(--color-accent);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: #d15440;
  }

  .btn-secondary {
    background: var(--color-grey);
    color: white;
  }

  .btn-secondary:hover:not(:disabled) {
    background: #5a6268;
  }

  .btn-danger {
    background: #dc3545;
    color: white;
  }

  .btn-danger:hover:not(:disabled) {
    background: #c82333;
  }

  .loading {
    text-align: center;
    padding: var(--spacing-xl);
    color: var(--color-text-secondary);
  }
</style>
