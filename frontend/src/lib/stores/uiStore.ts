/**
 * UI Store for global UI state
 */
import { writable } from 'svelte/store';

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
  duration?: number;
}

interface Modal {
  isOpen: boolean;
  type: 'success' | 'error' | 'warning' | 'info';
  title?: string;
  message: string | any;
  confirmText?: string;
  cancelText?: string;
  showCancel?: boolean;
  dismissible?: boolean;
  onConfirm?: () => void;
  onCancel?: () => void;
}

interface UIState {
  loading: boolean;
  toasts: Toast[];
  sidebarOpen: boolean;
  modal: Modal | null;
}

function createUIStore() {
  const { subscribe, set, update } = writable<UIState>({
    loading: false,
    toasts: [],
    sidebarOpen: true,
    modal: null,
  });

  let toastId = 0;

  return {
    subscribe,
    setLoading: (loading: boolean) => {
      update(state => ({ ...state, loading }));
    },
    showToast: (message: string, type: Toast['type'] = 'info', duration = 3000) => {
      const id = toastId++;
      const toast: Toast = { id, message, type, duration };
      
      update(state => ({
        ...state,
        toasts: [...state.toasts, toast],
      }));

      if (duration > 0) {
        setTimeout(() => {
          update(state => ({
            ...state,
            toasts: state.toasts.filter(t => t.id !== id),
          }));
        }, duration);
      }
    },
    removeToast: (id: number) => {
      update(state => ({
        ...state,
        toasts: state.toasts.filter(t => t.id !== id),
      }));
    },
    toggleSidebar: () => {
      update(state => ({ ...state, sidebarOpen: !state.sidebarOpen }));
    },
    showModal: (options: Omit<Modal, 'isOpen'>) => {
      update(state => ({
        ...state,
        modal: {
          isOpen: true,
          type: options.type || 'info',
          title: options.title,
          message: options.message,
          confirmText: options.confirmText,
          cancelText: options.cancelText,
          showCancel: options.showCancel,
          dismissible: options.dismissible,
          onConfirm: options.onConfirm,
          onCancel: options.onCancel,
        },
      }));
    },
    closeModal: () => {
      update(state => ({ ...state, modal: null }));
    },
    showAlert: (message: string, title?: string) => {
      update(state => ({
        ...state,
        modal: {
          isOpen: true,
          type: 'info',
          title: title || 'Alert',
          message,
          showCancel: false,
          dismissible: true,
        },
      }));
    },
    showError: (message: string, title?: string) => {
      update(state => ({
        ...state,
        modal: {
          isOpen: true,
          type: 'error',
          title: title || 'Error',
          message,
          showCancel: false,
          dismissible: true,
        },
      }));
    },
    showSuccess: (message: string, title?: string) => {
      update(state => ({
        ...state,
        modal: {
          isOpen: true,
          type: 'success',
          title: title || 'Success',
          message,
          showCancel: false,
          dismissible: true,
        },
      }));
    },
    showWarning: (message: string, title?: string) => {
      update(state => ({
        ...state,
        modal: {
          isOpen: true,
          type: 'warning',
          title: title || 'Warning',
          message,
          showCancel: false,
          dismissible: true,
        },
      }));
    },
    showConfirm: (
      message: string,
      onConfirm?: () => void,
      options?: {
        title?: string;
        type?: 'success' | 'error' | 'warning' | 'info';
        confirmText?: string;
        cancelText?: string;
      }
    ) => {
      update(state => ({
        ...state,
        modal: {
          isOpen: true,
          type: options?.type || 'warning',
          title: options?.title || 'Confirm',
          message,
          confirmText: options?.confirmText || 'Confirm',
          cancelText: options?.cancelText || 'Cancel',
          showCancel: true,
          dismissible: true,
          onConfirm,
        },
      }));
    },
  };
}

export const uiStore = createUIStore();
