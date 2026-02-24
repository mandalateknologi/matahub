/**
 * Authentication Store with Role-Based Access Control
 */
import { writable, derived } from 'svelte/store';
import type { User, UserRole } from '@/lib/types';
import { authAPI } from '../api/auth';

interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  loading: boolean;
}

function createAuthStore() {
  const { subscribe, set, update } = writable<AuthState>({
    isAuthenticated: authAPI.isAuthenticated(),
    user: null,
    loading: false,
  });

  return {
    subscribe,
    login: async (username: string, password: string) => {
      update(state => ({ ...state, loading: true }));
      try {
        await authAPI.login({ username, password });
        
        // Fetch user details after successful login
        const user = await authAPI.getCurrentUser();
        update(state => ({ 
          ...state, 
          isAuthenticated: true, 
          user,
          loading: false 
        }));
      } catch (error) {
        update(state => ({ ...state, loading: false }));
        throw error;
      }
    },
    
    logout: () => {
      authAPI.logout();
      set({ isAuthenticated: false, user: null, loading: false });
    },
    
    checkAuth: async () => {
      const isAuthenticated = authAPI.isAuthenticated();
      if (isAuthenticated) {
        try {
          const user = await authAPI.getCurrentUser();
          update(state => ({ ...state, isAuthenticated: true, user }));
        } catch (error) {
          // Token invalid, clear auth
          authAPI.logout();
          set({ isAuthenticated: false, user: null, loading: false });
        }
      } else {
        update(state => ({ ...state, isAuthenticated: false, user: null }));
      }
    },
    
    // Fetch current user details
    fetchUser: async () => {
      update(state => ({ ...state, loading: true }));
      try {
        const user = await authAPI.getCurrentUser();
        update(state => ({ ...state, user, loading: false }));
      } catch (error) {
        update(state => ({ ...state, loading: false }));
        throw error;
      }
    },
  };
}

export const authStore = createAuthStore();

// Derived stores for role-based access control
export const userRole = derived(authStore, $auth => $auth.user?.role || null);

export const isAdmin = derived(authStore, $auth => 
  $auth.user?.role === 'admin'
);

export const isProjectAdmin = derived(authStore, $auth => 
  $auth.user?.role === 'project_admin'
);

export const isOperator = derived(authStore, $auth => 
  $auth.user?.role === 'operator'
);

// Check if user can access data management features (datasets, projects, models, training)
export const canAccessDataManagement = derived(authStore, $auth => 
  $auth.user?.role === 'admin' || $auth.user?.role === 'project_admin'
);

// Check if user can access user management
export const canAccessUserManagement = derived(authStore, $auth => 
  $auth.user?.role === 'admin'
);

// Check if user can only access detection features
export const isDetectionOnly = derived(authStore, $auth => 
  $auth.user?.role === 'operator'
);

// Helper function to check resource ownership
export function isResourceOwner(creatorId: number | undefined, currentUserId: number | undefined): boolean {
  return creatorId !== undefined && currentUserId !== undefined && creatorId === currentUserId;
}

// Helper function to check if user can edit resource
export function canEditResource(
  creatorId: number | undefined, 
  currentUser: User | null,
  isSystemResource: boolean = false
): boolean {
  if (!currentUser) return false;
  
  // Admin can edit anything except system resources
  if (currentUser.role === 'admin' && !isSystemResource) return true;
  
  // System resources: only admin can delete, but project_admin can use
  if (isSystemResource) return false;
  
  // Project admin can edit their own resources
  if (currentUser.role === 'project_admin') {
    return isResourceOwner(creatorId, currentUser.id);
  }
  
  return false;
}

// Helper function to check if user can delete resource
export function canDeleteResource(
  creatorId: number | undefined,
  currentUser: User | null,
  isSystemResource: boolean = false
): boolean {
  if (!currentUser) return false;
  
  // Only admin can delete system resources (base models)
  if (isSystemResource) {
    return currentUser.role === 'admin';
  }
  
  // Admin can delete anything
  if (currentUser.role === 'admin') return true;
  
  // Project admin can delete their own resources
  if (currentUser.role === 'project_admin') {
    return isResourceOwner(creatorId, currentUser.id);
  }
  
  return false;
}
