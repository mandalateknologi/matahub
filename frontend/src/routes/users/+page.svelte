<script lang="ts">
  import { onMount } from "svelte";
  import { navigate } from "../../lib/router";
  import { usersAPI } from "../../lib/api/users";
  import { uiStore } from "../../lib/stores/uiStore";
  import { isAdmin } from "../../lib/stores/authStore";
  import LoadingSpinner from "../../lib/components/shared/LoadingSpinner.svelte";
  import type { UserWithResourceCounts, UserRole } from "@/lib/types";

  let loading = true;
  let users: UserWithResourceCounts[] = [];
  let filteredUsers: UserWithResourceCounts[] = [];

  // Filters
  let searchQuery = "";
  let roleFilter: UserRole | "all" = "all";
  let statusFilter: "all" | "active" | "inactive" = "all";
  let statsAnimated = false;
  let selectedStatFilter: string | null = null;

  // Modals
  let showCreateModal = false;
  let showEditModal = false;
  let editingUser: UserWithResourceCounts | null = null;

  // Forms
  let createForm = {
    email: "",
    password: "",
    role: "operator" as UserRole,
    first_name: "",
    last_name: "",
  };

  let editForm = {
    email: "",
    role: "" as UserRole | "",
    is_active: true,
    password: "",
    first_name: "",
    last_name: "",
  };

  $: if (!$isAdmin) {
    navigate("/home");
  }

  onMount(() => {
    loadUsers();
  });

  $: {
    // Apply filters
    filteredUsers = users.filter((user) => {
      // Search filter
      const matchesSearch =
        searchQuery === "" ||
        user.email.toLowerCase().includes(searchQuery.toLowerCase());

      // Role filter
      const matchesRole = roleFilter === "all" || user.role === roleFilter;

      // Status filter
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" && user.is_active) ||
        (statusFilter === "inactive" && !user.is_active);

      // Stat filter
      const matchesStatFilter =
        !selectedStatFilter ||
        (selectedStatFilter === "active" && user.is_active) ||
        (selectedStatFilter === "inactive" && !user.is_active) ||
        (selectedStatFilter === "admin" && user.role === "admin") ||
        (selectedStatFilter === "project_admin" &&
          user.role === "project_admin") ||
        (selectedStatFilter === "operator" && user.role === "operator");

      return matchesSearch && matchesRole && matchesStatus && matchesStatFilter;
    });
  }

  async function loadUsers() {
    try {
      loading = true;
      users = await usersAPI.list();
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to load users", "error");
    } finally {
      loading = false;
      // Trigger stats animation after data loads
      setTimeout(() => {
        statsAnimated = true;
      }, 100);
    }
  }

  function openCreateModal() {
    createForm = {
      email: "",
      password: "",
      role: "operator",
      first_name: "",
      last_name: "",
    };
    showCreateModal = true;
  }

  async function handleCreateUser() {
    try {
      await usersAPI.create(createForm);
      uiStore.showToast("User created successfully", "success");
      showCreateModal = false;
      await loadUsers();
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to create user", "error");
    }
  }

  function openEditModal(user: UserWithResourceCounts) {
    editingUser = user;
    editForm = {
      email: user.email,
      role: user.role,
      is_active: user.is_active,
      password: "",
      first_name: user.first_name || "",
      last_name: user.last_name || "",
    };
    showEditModal = true;
  }

  async function handleUpdateUser() {
    if (!editingUser) return;

    try {
      const updates: any = {};
      if (editForm.email !== editingUser.email) updates.email = editForm.email;
      if (editForm.role && editForm.role !== editingUser.role)
        updates.role = editForm.role;
      if (editForm.is_active !== editingUser.is_active)
        updates.is_active = editForm.is_active;
      if (editForm.password) updates.password = editForm.password;
      if (editForm.first_name !== (editingUser.first_name || "")) updates.first_name = editForm.first_name;
      if (editForm.last_name !== (editingUser.last_name || "")) updates.last_name = editForm.last_name;

      await usersAPI.update(editingUser.id, updates);
      uiStore.showToast("User updated successfully", "success");
      showEditModal = false;
      await loadUsers();
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to update user", "error");
    }
  }

  async function handleDeleteUser(
    user: UserWithResourceCounts,
    force: boolean = false
  ) {
    const hasResources = user.datasets_count > 0 || user.projects_count > 0;

    let message = `Are you sure you want to ${force ? "permanently delete" : "deactivate"} ${user.email}?`;
    if (force && hasResources) {
      message += `\n\nWARNING: This user owns ${user.datasets_count} datasets and ${user.projects_count} projects. This will fail unless resources are transferred first.`;
    } else if (!force) {
      message += "\n\nThe user will be deactivated but data will be preserved.";
    }

    if (!confirm(message)) return;

    try {
      await usersAPI.delete(user.id, force);
      uiStore.showToast(
        `User ${force ? "deleted" : "deactivated"} successfully`,
        "success"
      );
      await loadUsers();
    } catch (error: any) {
      uiStore.showToast(
        error.message || `Failed to ${force ? "delete" : "deactivate"} user`,
        "error"
      );
    }
  }

  async function handleReactivateUser(user: UserWithResourceCounts) {
    if (!confirm(`Reactivate ${user.email}?`)) return;

    try {
      await usersAPI.reactivate(user.id);
      uiStore.showToast("User reactivated successfully", "success");
      await loadUsers();
    } catch (error: any) {
      uiStore.showToast(error.message || "Failed to reactivate user", "error");
    }
  }

  function getRoleBadgeClass(role: UserRole): string {
    switch (role) {
      case "admin":
        return "badge-admin";
      case "project_admin":
        return "badge-project-admin";
      case "operator":
        return "badge-operator";
      default:
        return "";
    }
  }

  function getRoleIcon(role: UserRole): string {
    switch (role) {
      case "admin":
        return "👑";
      case "project_admin":
        return "📊";
      case "operator":
        return "🎯";
      default:
        return "👤";
    }
  }

  function formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleDateString();
  }

  function handleStatClick(filterType: string) {
    if (selectedStatFilter === filterType) {
      selectedStatFilter = null;
    } else {
      selectedStatFilter = filterType;
    }
  }

  function handleStatKeydown(event: KeyboardEvent, filterType: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleStatClick(filterType);
    }
  }

  // Computed statistics
  $: totalUsers = users.length;
  $: activeUsers = users.filter((u) => u.is_active).length;
  $: inactiveUsers = users.filter((u) => !u.is_active).length;
  $: adminUsers = users.filter((u) => u.role === "admin").length;
  $: projectAdminUsers = users.filter((u) => u.role === "project_admin").length;
  $: operatorUsers = users.filter((u) => u.role === "operator").length;

  // Auto-reset stat filter when other filters change
  $: if (searchQuery || roleFilter !== "all" || statusFilter !== "all") {
    selectedStatFilter = null;
  }
</script>

<div class="page">
  <div class="header">
    <div>
      <h1>User Management</h1>
      <p class="subtitle">Manage system users and their roles</p>
    </div>
    <button class="btn btn-primary" on:click={openCreateModal}>
      <span>➕ Create User</span>
    </button>
  </div>

  <!-- Statistics Cards -->
  {#if users.length > 0}
    <div class="stats-grid">
      <div
        class="stat-card"
        class:animate={statsAnimated}
        role="button"
        tabindex="0"
      >
        <div class="stat-icon">👥</div>
        <div class="stat-content">
          <div class="stat-value">{totalUsers}</div>
          <div class="stat-label">Total Users</div>
        </div>
      </div>

      <div
        class="stat-card clickable"
        class:animate={statsAnimated}
        class:active={selectedStatFilter === "active"}
        on:click={() => handleStatClick("active")}
        on:keydown={(e) => handleStatKeydown(e, "active")}
        role="button"
        tabindex="0"
      >
        <div class="stat-icon">✅</div>
        <div class="stat-content">
          <div class="stat-value">{activeUsers}</div>
          <div class="stat-label">Active</div>
        </div>
      </div>

      <div
        class="stat-card clickable"
        class:animate={statsAnimated}
        class:active={selectedStatFilter === "inactive"}
        on:click={() => handleStatClick("inactive")}
        on:keydown={(e) => handleStatKeydown(e, "inactive")}
        role="button"
        tabindex="0"
      >
        <div class="stat-icon">🚫</div>
        <div class="stat-content">
          <div class="stat-value">{inactiveUsers}</div>
          <div class="stat-label">Inactive</div>
        </div>
      </div>

      <div
        class="stat-card clickable"
        class:animate={statsAnimated}
        class:active={selectedStatFilter === "admin"}
        on:click={() => handleStatClick("admin")}
        on:keydown={(e) => handleStatKeydown(e, "admin")}
        role="button"
        tabindex="0"
      >
        <div class="stat-icon">👑</div>
        <div class="stat-content">
          <div class="stat-value">{adminUsers}</div>
          <div class="stat-label">Admins</div>
        </div>
      </div>

      <div
        class="stat-card clickable"
        class:animate={statsAnimated}
        class:active={selectedStatFilter === "project_admin"}
        on:click={() => handleStatClick("project_admin")}
        on:keydown={(e) => handleStatKeydown(e, "project_admin")}
        role="button"
        tabindex="0"
      >
        <div class="stat-icon">📊</div>
        <div class="stat-content">
          <div class="stat-value">{projectAdminUsers}</div>
          <div class="stat-label">Project Admins</div>
        </div>
      </div>

      <div
        class="stat-card clickable"
        class:animate={statsAnimated}
        class:active={selectedStatFilter === "operator"}
        on:click={() => handleStatClick("operator")}
        on:keydown={(e) => handleStatKeydown(e, "operator")}
        role="button"
        tabindex="0"
      >
        <div class="stat-icon">🎯</div>
        <div class="stat-content">
          <div class="stat-value">{operatorUsers}</div>
          <div class="stat-label">Operators</div>
        </div>
      </div>
    </div>
  {/if}

  <!-- Filters -->
  <div class="filters-card">
    <div class="filters-grid">
      <div class="filter-group">
        <label for="search">Search</label>
        <input
          id="search"
          type="text"
          placeholder="🔍 Search by email..."
          bind:value={searchQuery}
        />
      </div>

      <div class="filter-group">
        <label for="role-filter">Role</label>
        <select id="role-filter" bind:value={roleFilter}>
          <option value="all">All Roles</option>
          <option value="admin">Admin</option>
          <option value="project_admin">Project Admin</option>
          <option value="operator">Operator</option>
        </select>
      </div>

      <div class="filter-group">
        <label for="status-filter">Status</label>
        <select id="status-filter" bind:value={statusFilter}>
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>
    </div>
  </div>

  <!-- Users Table -->
  {#if loading}
    <LoadingSpinner />
  {:else if filteredUsers.length === 0}
    <div class="empty-state">
      <div class="empty-icon">👥</div>
      <h3>No Users Found</h3>
      <p>
        {searchQuery || roleFilter !== "all" || statusFilter !== "all"
          ? "Try adjusting your filters"
          : "Create your first user to get started"}
      </p>
    </div>
  {:else}
    <div class="table-container">
      <table class="users-table">
        <thead>
          <tr>
            <th>User</th>
            <th>Email</th>
            <th>Role</th>
            <th>Resources</th>
            <th>Status</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredUsers as user}
            <tr class:inactive={!user.is_active}>
              <td>
                <div class="user-cell">
                  <span class="user-icon">{getRoleIcon(user.role)}</span>
                  <span class="user-name">
                    {#if user.first_name || user.last_name}
                      {user.first_name} {user.last_name}
                    {:else}
                      {user.email.split("@")[0]}
                    {/if}
                  </span>
                </div>
              </td>
              <td>{user.email}</td>
              <td>
                <span class="role-badge {getRoleBadgeClass(user.role)}">
                  {user.role.replace("_", " ").toUpperCase()}
                </span>
              </td>
              <td>
                <div class="resources-cell">
                  <span class="resource-badge" title="Datasets"
                    >📁 {user.datasets_count}</span
                  >
                  <span class="resource-badge" title="Projects"
                    >📊 {user.projects_count}</span
                  >
                  <span class="resource-badge" title="Prediction Jobs"
                    >🎯 {user.prediction_jobs_count}</span
                  >
                </div>
              </td>
              <td>
                <span
                  class="status-badge"
                  class:status-active={user.is_active}
                  class:status-inactive={!user.is_active}
                >
                  {user.is_active ? "Active" : "Inactive"}
                </span>
              </td>
              <td>{formatDate(user.created_at)}</td>
              <td>
                <div class="action-buttons">
                  {#if user.is_active}
                    <button
                      class="btn-icon"
                      title="Edit"
                      on:click={() => openEditModal(user)}
                    >
                      ✏️
                    </button>
                    <button
                      class="btn-icon btn-danger"
                      title="Deactivate"
                      on:click={() => handleDeleteUser(user, false)}
                    >
                      🚫
                    </button>
                    {#if user.datasets_count === 0 && user.projects_count === 0}
                      <button
                        class="btn-icon btn-danger"
                        title="Delete Permanently"
                        on:click={() => handleDeleteUser(user, true)}
                      >
                        🗑️
                      </button>
                    {/if}
                  {:else}
                    <button
                      class="btn-icon btn-success"
                      title="Reactivate"
                      on:click={() => handleReactivateUser(user)}
                    >
                      ✅
                    </button>
                  {/if}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="table-footer">
      <p>Showing {filteredUsers.length} of {users.length} users</p>
    </div>
  {/if}
</div>

<!-- Create User Modal -->
{#if showCreateModal}
  <div
    class="modal-overlay"
    on:click={() => (showCreateModal = false)}
    role="button"
    tabindex="0"
    on:keydown={(e) => e.key === "Escape" && (showCreateModal = false)}
  >
    <div
      class="modal-content"
      on:click|stopPropagation
      role="dialog"
      tabindex="-1"
    >
      <div class="modal-header">
        <h3>Create New User</h3>
        <button class="modal-close" on:click={() => (showCreateModal = false)}
          >✕</button
        >
      </div>
      <div class="modal-body">
        <form on:submit|preventDefault={handleCreateUser}>
          <div class="form-group">
            <label for="create-email">Email *</label>
            <input
              id="create-email"
              type="email"
              bind:value={createForm.email}
              placeholder="Enter email"
              required
            />
          </div>

          <div class="form-group">
            <label for="create-first-name">First Name</label>
            <input
              id="create-first-name"
              type="text"
              bind:value={createForm.first_name}
              placeholder="Enter first name"
              maxlength="100"
            />
          </div>

          <div class="form-group">
            <label for="create-last-name">Last Name</label>
            <input
              id="create-last-name"
              type="text"
              bind:value={createForm.last_name}
              placeholder="Enter last name"
              maxlength="100"
            />
          </div>

          <div class="form-group">
            <label for="create-password">Password *</label>
            <input
              id="create-password"
              type="password"
              bind:value={createForm.password}
              placeholder="Enter password"
              required
              minlength="6"
            />
            <small>Minimum 6 characters</small>
          </div>

          <div class="form-group">
            <label for="create-role">Role *</label>
            <select id="create-role" bind:value={createForm.role} required>
              <option value="project_admin"
                >📊 Project Admin - Manage datasets, projects, models</option
              >
              <option value="operator">🎯 Operator - Detection only</option>
            </select>
            <small
              >Admins can only be created by other admins through direct
              database access</small
            >
          </div>

          <div class="modal-actions">
            <button
              type="button"
              class="btn btn-secondary"
              on:click={() => (showCreateModal = false)}
            >
              Cancel
            </button>
            <button type="submit" class="btn btn-primary"> Create User </button>
          </div>
        </form>
      </div>
    </div>
  </div>
{/if}

<!-- Edit User Modal -->
{#if showEditModal && editingUser}
  <div
    class="modal-overlay"
    on:click={() => (showEditModal = false)}
    role="button"
    tabindex="0"
    on:keydown={(e) => e.key === "Escape" && (showEditModal = false)}
  >
    <div
      class="modal-content"
      on:click|stopPropagation
      role="dialog"
      tabindex="-1"
    >
      <div class="modal-header">
        <h3>Edit User: {editingUser.email}</h3>
        <button class="modal-close" on:click={() => (showEditModal = false)}
          >✕</button
        >
      </div>
      <div class="modal-body">
        <form on:submit|preventDefault={handleUpdateUser}>
          <div class="form-group">
            <label for="edit-email">Email</label>
            <input
              id="edit-email"
              type="email"
              bind:value={editForm.email}
              placeholder="Enter email"
            />
          </div>

          <div class="form-group">
            <label for="edit-first-name">First Name</label>
            <input
              id="edit-first-name"
              type="text"
              bind:value={editForm.first_name}
              placeholder="Enter first name"
              maxlength="100"
            />
          </div>

          <div class="form-group">
            <label for="edit-last-name">Last Name</label>
            <input
              id="edit-last-name"
              type="text"
              bind:value={editForm.last_name}
              placeholder="Enter last name"
              maxlength="100"
            />
          </div>

          <div class="form-group">
            <label for="edit-role">Role</label>
            <select id="edit-role" bind:value={editForm.role}>
              <option value="admin">👑 Admin - Full access</option>
              <option value="project_admin"
                >📊 Project Admin - Manage data</option
              >
              <option value="operator">🎯 Operator - Detection only</option>
            </select>
            {#if editingUser.datasets_count > 0 || editingUser.projects_count > 0}
              <small class="warning"
                >⚠️ User owns {editingUser.datasets_count} datasets and {editingUser.projects_count}
                projects. Cannot downgrade to Operator.</small
              >
            {/if}
          </div>

          <div class="form-group">
            <label for="edit-password">New Password (optional)</label>
            <input
              id="edit-password"
              type="password"
              bind:value={editForm.password}
              placeholder="Leave blank to keep current password"
              minlength="6"
            />
            <small>Only fill this if you want to change the password</small>
          </div>

          <div class="form-group checkbox-group">
            <label>
              <input type="checkbox" bind:checked={editForm.is_active} />
              <span>Active User</span>
            </label>
            <small>Inactive users cannot log in</small>
          </div>

          <div class="modal-actions">
            <button
              type="button"
              class="btn btn-secondary"
              on:click={() => (showEditModal = false)}
            >
              Cancel
            </button>
            <button type="submit" class="btn btn-primary"> Update User </button>
          </div>
        </form>
      </div>
    </div>
  </div>
{/if}

<style>
  .page {
    width: 100%;
    height: 100%;
    padding: var(--spacing-lg);
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-xl);
  }

  h1 {
    color: var(--color-navy);
    margin: 0;
    font-size: 2rem;
  }

  .subtitle {
    color: var(--color-text-light);
    margin-top: var(--spacing-xs);
  }

  /* Keyframe Animations */
  @keyframes fadeInCard {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes countUp {
    from {
      opacity: 0;
      transform: scale(0.5);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }

  /* Statistics Cards */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--spacing-lg);
    margin-bottom: var(--spacing-xl);
  }

  .stat-card {
    background: var(--color-bg-card);
    padding: var(--spacing-lg);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    transition: all var(--transition-base);
    opacity: 0;
    border: 2px solid transparent;
  }

  .stat-card.animate {
    animation: fadeInCard 0.5s ease forwards;
  }

  .stat-card:nth-child(1) {
    animation-delay: 0s;
  }

  .stat-card:nth-child(2) {
    animation-delay: 0.1s;
  }

  .stat-card:nth-child(3) {
    animation-delay: 0.2s;
  }

  .stat-card:nth-child(4) {
    animation-delay: 0.3s;
  }

  .stat-card:nth-child(5) {
    animation-delay: 0.4s;
  }

  .stat-card:nth-child(6) {
    animation-delay: 0.5s;
  }

  .stat-card.clickable {
    cursor: pointer;
  }

  .stat-card.clickable:hover {
    transform: translateY(-4px);
    box-shadow: var(--shadow-md);
  }

  .stat-card.clickable:active {
    transform: translateY(-2px);
  }

  .stat-card.active {
    border-color: var(--color-accent);
    box-shadow: 0 0 0 3px rgba(225, 96, 76, 0.1);
  }

  .stat-icon {
    font-size: 2rem;
    line-height: 1;
  }

  .stat-content {
    flex: 1;
  }

  .stat-value {
    font-size: var(--font-size-2xl);
    font-weight: 700;
    color: var(--color-navy);
    line-height: 1;
  }

  .stat-card.animate .stat-value {
    animation: countUp 0.6s ease forwards;
    animation-delay: inherit;
  }

  .stat-label {
    font-size: var(--font-size-sm);
    color: var(--color-grey);
    margin-top: var(--spacing-xs);
    font-weight: 500;
  }

  /* Filters */
  .filters-card {
    background: var(--color-white);
    padding: var(--spacing-lg);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    margin-bottom: var(--spacing-lg);
  }

  .filters-grid {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr;
    gap: var(--spacing-md);
  }

  .filter-group {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .filter-group label {
    font-weight: 600;
    font-size: var(--font-size-sm);
    color: var(--color-navy);
  }

  .filter-group input,
  .filter-group select {
    padding: var(--spacing-sm) var(--spacing-md);
    border: 2px solid var(--color-border);
    border-radius: var(--radius-md);
    font-size: var(--font-size-base);
    transition: all var(--transition-fast);
    background: var(--color-white);
  }

  .filter-group input:focus,
  .filter-group select:focus {
    outline: none;
    border-color: var(--color-accent);
    box-shadow: 0 0 0 3px rgba(225, 96, 76, 0.1);
  }

  /* Table */
  .table-container {
    background: var(--color-white);
    border-radius: 8px;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
  }

  .users-table {
    width: 100%;
    border-collapse: collapse;
  }

  .users-table thead {
    background-color: var(--color-bg-light1);
  }

  .users-table th {
    padding: var(--spacing-md);
    text-align: left;
    font-weight: 600;
    color: var(--color-navy);
    border-bottom: 2px solid var(--color-border);
    font-size: var(--font-size-sm);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .users-table td {
    padding: var(--spacing-md);
    border-bottom: 1px solid var(--color-border);
  }

  .users-table tbody tr:hover {
    background-color: var(--color-bg-light1);
  }

  .users-table tbody tr.inactive {
    opacity: 0.6;
    background-color: #fef2f2;
  }

  .user-cell {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
  }

  .user-icon {
    font-size: 1.5rem;
  }

  .user-name {
    font-weight: 500;
    color: var(--color-navy);
  }

  .role-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .badge-admin {
    background-color: #fef3c7;
    color: #92400e;
  }

  .badge-project-admin {
    background-color: #dbeafe;
    color: #1e40af;
  }

  .badge-operator {
    background-color: #e0f2fe;
    color: #0369a1;
  }

  .resources-cell {
    display: flex;
    gap: var(--spacing-xs);
  }

  .resource-badge {
    font-size: var(--font-size-sm);
    color: var(--color-text-light);
  }

  .status-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: var(--font-size-xs);
    font-weight: 600;
  }

  .status-active {
    background-color: #d1fae5;
    color: #065f46;
  }

  .status-inactive {
    background-color: #fee2e2;
    color: #991b1b;
  }

  .action-buttons {
    display: flex;
    gap: var(--spacing-xs);
  }

  .btn-icon {
    background: transparent;
    border: none;
    font-size: 1.2rem;
    cursor: pointer;
    padding: var(--spacing-xs);
    border-radius: 4px;
    transition: background-color var(--transition-fast);
  }

  .btn-icon:hover {
    background-color: var(--color-bg-light1);
  }

  .btn-icon.btn-danger:hover {
    background-color: #fee2e2;
  }

  .btn-icon.btn-success:hover {
    background-color: #d1fae5;
  }

  .table-footer {
    padding: var(--spacing-md);
    background: var(--color-white);
    border-top: 1px solid var(--color-border);
    text-align: center;
    color: var(--color-text-light);
    font-size: var(--font-size-sm);
  }

  /* Empty State */
  .empty-state {
    background: var(--color-white);
    padding: var(--spacing-xxl);
    border-radius: 8px;
    text-align: center;
    box-shadow: var(--shadow-sm);
  }

  .empty-icon {
    font-size: 4rem;
    margin-bottom: var(--spacing-md);
  }

  .empty-state h3 {
    color: var(--color-navy);
    margin-bottom: var(--spacing-sm);
  }

  .empty-state p {
    color: var(--color-text-light);
  }

  /* Modal */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal-content {
    background: var(--color-white);
    border-radius: 8px;
    max-width: 500px;
    width: 90%;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: var(--shadow-lg);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-lg);
    border-bottom: 1px solid var(--color-border);
  }

  .modal-header h3 {
    margin: 0;
    color: var(--color-navy);
  }

  .modal-close {
    background: transparent;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: var(--color-text-light);
  }

  .modal-body {
    padding: var(--spacing-lg);
  }

  .form-group {
    margin-bottom: var(--spacing-md);
  }

  .form-group label {
    display: block;
    margin-bottom: var(--spacing-xs);
    font-weight: 600;
    color: var(--color-navy);
  }

  .form-group input,
  .form-group select {
    width: 100%;
    padding: var(--spacing-sm);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    font-size: var(--font-size-base);
  }

  .form-group small {
    display: block;
    margin-top: var(--spacing-xs);
    color: var(--color-text-light);
    font-size: var(--font-size-sm);
  }

  .form-group small.warning {
    color: #d97706;
  }

  .checkbox-group label {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    cursor: pointer;
  }

  .checkbox-group input[type="checkbox"] {
    width: auto;
    cursor: pointer;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--spacing-sm);
    margin-top: var(--spacing-lg);
  }

  /* Responsive Design */
  @media (max-width: 1400px) {
    .filters-grid {
      grid-template-columns: 1fr 1fr 1fr;
    }
  }

  @media (max-width: 1024px) {
    .page {
      padding: var(--spacing-md);
    }

    .stats-grid {
      grid-template-columns: repeat(3, 1fr);
    }

    .filters-grid {
      grid-template-columns: 1fr;
    }

    .table-container {
      overflow-x: auto;
    }

    .users-table th,
    .users-table td {
      padding: var(--spacing-sm);
    }
  }

  @media (max-width: 768px) {
    .page {
      padding: var(--spacing-sm);
    }

    .header {
      flex-direction: column;
      align-items: flex-start;
      gap: var(--spacing-md);
    }

    .stats-grid {
      grid-template-columns: repeat(2, 1fr);
      gap: var(--spacing-md);
    }

    .stat-card {
      padding: var(--spacing-md);
    }

    .stat-icon {
      font-size: 1.5rem;
    }

    .stat-value {
      font-size: var(--font-size-xl);
    }

    .filters-card {
      padding: var(--spacing-md);
    }

    .users-table th:nth-child(4),
    .users-table td:nth-child(4) {
      display: none; /* Hide Resources column on mobile */
    }

    .users-table th:nth-child(6),
    .users-table td:nth-child(6) {
      display: none; /* Hide Created column on mobile */
    }

    .user-name {
      font-size: var(--font-size-sm);
    }

    .action-buttons {
      flex-direction: column;
    }

    .modal-content {
      width: 95%;
      max-height: 95vh;
    }
  }

  @media (max-width: 480px) {
    h1 {
      font-size: 1.5rem;
    }

    .stats-grid {
      grid-template-columns: 1fr;
    }

    .stat-card {
      padding: var(--spacing-sm) var(--spacing-md);
    }

    .filters-grid {
      gap: var(--spacing-sm);
    }

    .users-table {
      font-size: var(--font-size-sm);
    }

    .users-table th,
    .users-table td {
      padding: var(--spacing-xs) var(--spacing-sm);
    }

    .role-badge,
    .status-badge {
      font-size: 0.65rem;
      padding: 3px 8px;
    }
  }
</style>
