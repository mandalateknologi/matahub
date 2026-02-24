/**
 * Filter State Management with localStorage
 */

export interface PredictionFilters {
  selectedProject: number | string | null;
  selectedDataset: number | string | null;
  selectedModel: number | string | null;
  selectedStatus: string | null;
  selectedMode: string | null;
  selectedDatePreset: string;
  selectedTaskType: string | null;
  startDate: string;
  endDate: string;
  searchTerm: string;
  view: 'card' | 'list';
  currentPage: number;
  sortColumn: string | null;
  sortOrder: 'asc' | 'desc';
}

const STORAGE_KEY = 'prediction_filters';

/**
 * Load filters from localStorage
 */
export function loadFilters(): Partial<PredictionFilters> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (error) {
    console.error('Failed to load filters from localStorage:', error);
  }
  return {};
}

/**
 * Save filters to localStorage
 */
export function saveFilters(filters: Partial<PredictionFilters>): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
  } catch (error) {
    console.error('Failed to save filters to localStorage:', error);
  }
}

/**
 * Clear filters from localStorage
 */
export function clearStoredFilters(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (error) {
    console.error('Failed to clear filters from localStorage:', error);
  }
}

/**
 * Debounce function for search input
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null;
  
  return function(...args: Parameters<T>) {
    if (timeout) {
      clearTimeout(timeout);
    }
    
    timeout = setTimeout(() => {
      func(...args);
      timeout = null;
    }, wait);
  };
}
