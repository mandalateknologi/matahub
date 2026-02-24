<script lang="ts">
  import { link, location } from "svelte-spa-router";
  import { navigate } from "../../router";
  import { uiStore } from "../../stores/uiStore";
  import {
    authStore,
    canAccessDataManagement,
    canAccessUserManagement,
    isDetectionOnly,
  } from "../../stores/authStore";
  import { profileAPI } from "../../api/profile";

  let sidebarOpen = true;
  let showUserMenu = false;

  uiStore.subscribe((state) => {
    sidebarOpen = state.sidebarOpen;
  });

  $: user = $authStore.user;
  $: isDataManager = $canAccessDataManagement;
  $: isAdmin = $canAccessUserManagement;
  $: isOperatorOnly = $isDetectionOnly;

  // Track current location for active state
  $: currentPath = $location;

  // Helper function to check if a path is active
  function isActive(itemPath: string, currentLoc: string): boolean {
    // Exact match
    if (itemPath === currentLoc) return true;

    // Handle root/home paths
    if (
      (itemPath === "/home" || itemPath === "/") &&
      (currentLoc === "/" || currentLoc === "/home")
    ) {
      return true;
    }

    // Only highlight parent routes for nested pages that don't have their own menu item
    // For example: /datasets should be active for /datasets/123
    if (currentLoc.startsWith(itemPath + "/") && itemPath !== "/") {
      // Check if there's a more specific menu item that matches
      const hasMoreSpecificMatch = allNavItems.some(
        (navItem) =>
          navItem.path !== itemPath && currentLoc.startsWith(navItem.path)
      );

      // Only activate parent if no more specific match exists
      if (!hasMoreSpecificMatch) {
        return true;
      }
    }

    return false;
  }

  // Define all navigation items with role requirements
  interface NavItem {
    path?: string;
    label: string;
    icon?: string;
    roles?: string[]; // If undefined, visible to all
    type?: "separator"; // For category separators
  }

  const allNavItems: NavItem[] = [
    { path: "/home", label: "Home", icon: "🏠" },
    { label: "Machine Learning", type: "separator" },
    {
      path: "/datasets",
      label: "Datasets",
      icon: "📁",
      roles: ["admin", "project_admin"],
    },
    {
      path: "/training",
      label: "Training",
      icon: "🚀",
      roles: ["admin", "project_admin"],
    },
    {
      path: "/projects",
      label: "Projects",
      icon: "📊",
      roles: ["admin", "project_admin"],
    },
    {
      path: "/models",
      label: "Models",
      icon: "🤖",
      roles: ["admin", "project_admin"],
    },
    { label: "Tasks", type: "separator" },
    { path: "/predictions", label: "Predictions", icon: "🎯" },
    {
      path: "/recognition-catalogs",
      label: "Recognition",
      icon: "🎭",
      roles: ["admin", "project_admin"],
    },
    { path: "/visionmask", label: "VisionMask", icon: "🎨" },
    { label: "Operations", type: "separator" },
    {
      path: "/playbooks",
      label: "Playbooks",
      icon: "📖",
      roles: ["admin"],
    },
    { path: "/campaigns", label: "Campaigns", icon: "📁" },
    {
      path: "/workflows",
      label: "Workflows",
      icon: "🔄",
      roles: ["admin", "project_admin"],
    },
    // { path: "/predictions/reports", label: "Reports", icon: "📈" },
  ];

  const footerNavItems: NavItem[] = [
    { path: "/users", label: "Users", icon: "👥", roles: ["admin"] },
    { path: "/files", label: "File Manager", icon: "📂" },
    { path: "/settings", label: "Settings", icon: "⚙️" },
  ];

  function toggleUserMenu() {
    showUserMenu = !showUserMenu;
  }

  function handleLogout() {
    showUserMenu = false;
    authStore.logout();
    navigate("/login", { replace: true });
  }

  function closeUserMenu() {
    showUserMenu = false;
  }

  function getUserInitials(email: string): string {
    if (!email) return "U";
    
    // Use first and last name if available
    if (user?.first_name || user?.last_name) {
      const firstInitial = user.first_name ? user.first_name.charAt(0).toUpperCase() : "";
      const lastInitial = user.last_name ? user.last_name.charAt(0).toUpperCase() : "";
      return firstInitial + lastInitial || firstInitial || "U";
    }
    
    // Fallback to email
    const name = email.split("@")[0];
    return name.substring(0, 1).toUpperCase();
  }

  function getUserDisplayName(): string {
    if (!user) return "";
    
    // Use full name if available
    if (user.first_name && user.last_name) {
      return `${user.first_name} ${user.last_name}`;
    } else if (user.first_name) {
      return user.first_name;
    }
    
    // Fallback to email username
    return user.email.split("@")[0];
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

  // Filter nav items based on user role
  $: navItems = allNavItems.filter((item) => {
    if (!item.roles) return true; // No role restriction
    if (!user) return false; // Not logged in
    return item.roles.includes(user.role);
  });

  $: footerItems = footerNavItems.filter((item) => {
    if (!item.roles) return true; // No role restriction
    if (!user) return false; // Not logged in
    return item.roles.includes(user.role);
  });
</script>

<aside class="sidebar" class:open={sidebarOpen}>
  <nav class="sidebar-nav">
    {#each navItems as item}
      {#if item.type === "separator"}
        {#if sidebarOpen}
          <div class="nav-separator">
            <span class="separator-label">{item.label}</span>
          </div>
        {:else}
          <div class="nav-separator-collapsed"></div>
        {/if}
      {:else}
        <a
          href={item.path}
          use:link
          class="nav-item"
          class:active={isActive(item.path, currentPath)}
        >
          <span class="nav-icon">{item.icon}</span>
          {#if sidebarOpen}
            <span class="nav-label">{item.label}</span>
            {#if isOperatorOnly && !item.roles}
              <span class="badge">Available</span>
            {/if}
          {/if}
        </a>
      {/if}
    {/each}
  </nav>

  <div class="sidebar-footer">
    {#each footerItems as item}
      <a
        href={item.path}
        use:link
        class="nav-item"
        class:active={isActive(item.path, currentPath)}
      >
        <span class="nav-icon">{item.icon}</span>
        {#if sidebarOpen}
          <span class="nav-label">{item.label}</span>
        {/if}
      </a>
    {/each}

    {#if user}
      <div class="user-profile-container">
        <button class="user-profile" on:click={toggleUserMenu}>
          <div class="user-avatar">
            {#if user.profile_image}
              <img src={profileAPI.getProfileImageUrl(user)} alt="Profile" />
            {:else}
              {getUserInitials(user.email)}
            {/if}
          </div>
          {#if sidebarOpen}
            <div class="user-details">
              <span class="user-name">{getUserDisplayName()}</span>
              <span class="user-email">{user.email}</span>
            </div>
            <span class="user-menu-icon">⋮</span>
          {/if}
        </button>

        {#if showUserMenu}
          <div class="user-menu" role="menu" on:click={closeUserMenu} on:keydown={closeUserMenu}>
            <div class="user-menu-header">
              <div class="user-avatar large">
                {#if user.profile_image}
                  <img src={profileAPI.getProfileImageUrl(user)} alt="Profile" />
                {:else}
                  {getUserInitials(user.email)}
                {/if}
              </div>
              <div class="user-menu-info">
                <span class="user-menu-name">{getUserDisplayName()}</span>
                <span class="user-menu-email">{user.email}</span>
                <span class="user-menu-role">{getRoleBadge(user.role)}</span>
              </div>
            </div>
            <div class="user-menu-divider"></div>
            <a href="/profile" use:link class="user-menu-item">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
              Profile
            </a>
            <a href="/settings" use:link class="user-menu-item">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M12 1v6m0 6v6m5.2-13.2L13 10m-2 4l-4.2 4.2M23 12h-6m-6 0H1m18.2 5.2L10 13m-4-2L1.8 6.8"></path>
              </svg>
              Settings
            </a>
            <button class="user-menu-item" on:click={handleLogout}>
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
              Log out
            </button>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</aside>

<style>
  .sidebar {
    background-color: var(--color-white);
    width: 65px;
    transition: width var(--transition-base);
    overflow-x: hidden;
    box-shadow: var(--shadow-md);
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .sidebar.open {
    width: 240px;
  }

  .sidebar-nav {
    display: flex;
    flex-direction: column;
    padding: 0;
    flex: 1;
  }

  .sidebar-footer {
    margin-top: auto;
    border-top: 1px solid var(--color-bg-light1);
  }

  .user-profile-container {
    position: relative;
    padding: var(--spacing-sm);
  }

  .user-profile {
    display: flex;
    align-items: center;
    width: 100%;
    padding: var(--spacing-sm);
    background: transparent;
    border: none;
    cursor: pointer;
    border-radius: var(--border-radius-md);
    transition: background-color var(--transition-fast);
    color: var(--color-navy);
    gap: var(--spacing-sm);
  }

  .user-profile:hover {
    background-color: var(--color-bg-light1);
  }

  .user-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--color-accent), #ff8a75);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    font-size: var(--font-size-sm);
    flex-shrink: 0;
    overflow: hidden;
  }

  .user-avatar img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .user-avatar.large {
    width: 40px;
    height: 40px;
    font-size: var(--font-size-base);
  }

  .user-details {
    display: flex;
    flex-direction: column;
    flex: 1;
    overflow: hidden;
    text-align: left;
  }

  .user-name {
    font-size: var(--font-size-sm);
    font-weight: 600;
    color: var(--color-navy);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .user-email {
    font-size: var(--font-size-xs);
    color: var(--color-text-light);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .user-menu-icon {
    font-size: var(--font-size-xl);
    color: var(--color-text-light);
    transform: rotate(90deg);
  }

  .user-menu {
    position: absolute;
    bottom: 100%;
    left: var(--spacing-sm);
    right: var(--spacing-sm);
    background-color: var(--color-white);
    border-radius: var(--border-radius-lg);
    box-shadow: var(--shadow-lg);
    margin-bottom: var(--spacing-sm);
    z-index: 1000;
    min-width: 240px;
    overflow: hidden;
  }

  .sidebar:not(.open) .user-menu {
    left: 70px;
    right: auto;
  }

  .user-menu-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    padding: var(--spacing-md);
    background: linear-gradient(135deg, rgba(225, 96, 76, 0.05), rgba(225, 96, 76, 0.1));
  }

  .user-menu-info {
    display: flex;
    flex-direction: column;
    flex: 1;
    overflow: hidden;
  }

  .user-menu-name {
    font-size: var(--font-size-base);
    font-weight: 600;
    color: var(--color-navy);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .user-menu-email {
    font-size: var(--font-size-xs);
    color: var(--color-text-light);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .user-menu-role {
    font-size: var(--font-size-xs);
    color: var(--color-accent);
    font-weight: 600;
    margin-top: var(--spacing-xs);
  }

  .user-menu-divider {
    height: 1px;
    background-color: var(--color-bg-light1);
    margin: var(--spacing-xs) 0;
  }

  .user-menu-item {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    padding: var(--spacing-sm) var(--spacing-md);
    color: var(--color-navy);
    text-decoration: none;
    transition: background-color var(--transition-fast);
    cursor: pointer;
    border: none;
    background: transparent;
    width: 100%;
    text-align: left;
    font-size: var(--font-size-sm);
  }

  .user-menu-item:hover {
    background-color: var(--color-bg-light1);
  }

  .user-menu-item svg {
    color: var(--color-text-light);
  }

  :global(.sidebar .nav-item) {
    display: flex;
    align-items: center;
    padding: var(--spacing-sm) var(--spacing-sm);
    color: var(--color-navy);
    text-decoration: none;
    transition: all var(--transition-base);
    white-space: nowrap;
    position: relative;
    border-radius: var(--radius-md);
    margin: 6px 10px;
    border: 2px solid transparent;
  }

  :global(.sidebar .nav-item:hover) {
    background: linear-gradient(
      135deg,
      rgba(225, 96, 76, 0.08) 0%,
      rgba(225, 96, 76, 0.12) 100%
    );
    border-color: rgba(225, 96, 76, 0.3);
    transform: translateX(6px) scale(1.01);
    box-shadow: 0 2px 8px rgba(225, 96, 76, 0.15);
  }

  :global(.sidebar .nav-item:active) {
    transform: translateX(4px) scale(0.99);
    background: linear-gradient(
      135deg,
      rgba(225, 96, 76, 0.15) 0%,
      rgba(225, 96, 76, 0.2) 100%
    );
  }

  :global(.sidebar .nav-item.active),
  :global(.sidebar .nav-item[aria-current="page"]) {
    background: rgba(225, 96, 76, 0.1);
    color: var(--color-accent);
    font-weight: 600;
    /* border-left: 3px solid var(--color-accent); */
  }

  :global(.sidebar .nav-item.active::before),
  :global(.sidebar .nav-item[aria-current="page"]::before) {
    content: "";
    position: absolute;
    left: -10px;
    top: 50%;
    transform: translateY(-50%);
    width: 3px;
    height: 50%;
    background: var(--color-accent);
    border-radius: 0 2px 2px 0;
  }

  :global(.sidebar .nav-item.active:hover),
  :global(.sidebar .nav-item[aria-current="page"]:hover) {
    background: rgba(225, 96, 76, 0.15);
  }

  :global(.sidebar .nav-item.active:active),
  :global(.sidebar .nav-item[aria-current="page"]:active) {
    background: rgba(225, 96, 76, 0.12);
  }

  .nav-icon {
    font-size: var(--font-size-xl);
    min-width: 28px;
    transition: all var(--transition-base);
  }

  :global(.sidebar .nav-item:hover) .nav-icon {
    transform: scale(1.1);
  }

  :global(.sidebar .nav-item.active) .nav-icon,
  :global(.sidebar .nav-item[aria-current="page"]) .nav-icon {
    transform: scale(1.05);
  }

  .nav-label {
    margin-left: var(--spacing-md);
    font-weight: 500;
    flex: 1;
    transition: all var(--transition-base);
  }

  :global(.sidebar .nav-item:hover) .nav-label {
    font-weight: 600;
  }

  :global(.sidebar .nav-item.active) .nav-label,
  :global(.sidebar .nav-item[aria-current="page"]) .nav-label {
    font-weight: 600;
  }

  /* Separator styles */
  .nav-separator {
    /* padding: var(--spacing-md) var(--spacing-sm); */
    margin: var(--spacing-sm) 5px;
    border-top: 1px solid var(--color-bg-light1);
    padding-left: var(--spacing-sm);
    padding-top: var(--spacing-sm);
  }

  .separator-label {
    font-size: var(--font-size-xs);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--color-text-light);
  }

  .nav-separator-collapsed {
    height: 1px;
    background-color: var(--color-bg-light1);
    margin: var(--spacing-md) 10px;
  }

  /* dge {
    background-color: var(--color-accent);
    color: var(--color-white);
    font-size: var(--font-size-xs);
    padding: 2px 8px;
    border-radius: 12px;
    font-weight: 600;
    margin-left: var(--spacing-sm);
  }

  /* Focus states for accessibility */
  :global(.sidebar .nav-item:focus) {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    background: linear-gradient(
      135deg,
      rgba(225, 96, 76, 0.06) 0%,
      rgba(225, 96, 76, 0.1) 100%
    );
  }

  :global(.sidebar .nav-item.active:focus),
  :global(.sidebar .nav-item[aria-current="page"]:focus) {
    outline: 3px solid var(--color-white);
    outline-offset: 3px;
  }

  /* Collapsed sidebar active state adjustments */
  .sidebar:not(.open) :global(.nav-item.active),
  .sidebar:not(.open) :global(.nav-item[aria-current="page"]) {
    border-left: none;
    border-bottom: 3px solid var(--color-accent);
  }

  .sidebar:not(.open) :global(.nav-item.active::before),
  .sidebar:not(.open) :global(.nav-item[aria-current="page"]::before) {
    display: none;
  }

  /* Responsive adjustments for mobile */
  @media (max-width: 768px) {
    .sidebar {
      width: 60px;
    }

    .sidebar.open {
      width: 200px;
    }

    :global(.sidebar .nav-item) {
      padding: var(--spacing-sm) var(--spacing-md);
      margin: 4px 6px;
    }

    :global(.sidebar .nav-item.active),
    :global(.sidebar .nav-item[aria-current="page"]) {
      transform: none;
    }

    :global(.sidebar .nav-item:hover) {
      transform: translateX(4px);
    }
  }

  @media (max-width: 480px) {
    :global(.sidebar .nav-item.active),
    :global(.sidebar .nav-item[aria-current="page"]) {
      box-shadow: none;
    }
  }

  /* Reduced motion for accessibility */
  @media (prefers-reduced-motion: reduce) {
    :global(.sidebar .nav-item),
    .nav-icon,
    .nav-label {
      transition: none;
      animation: none !important;
    }

    :global(.sidebar .nav-item.active),
    :global(.sidebar .nav-item[aria-current="page"]),
    :global(.sidebar .nav-item:hover) {
      transform: none;
      animation: none !important;
    }
  }
</style>
