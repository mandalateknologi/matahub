/**
 * Date Range Utilities for Detection Filters
 */

export type DatePreset = 
  | 'all' 
  | 'today' 
  | 'last3days' 
  | 'last7days' 
  | 'thisweek' 
  | 'thismonth' 
  | 'thisyear' 
  | 'custom';

export interface DateRange {
  start: string; // ISO date string (YYYY-MM-DD)
  end: string;   // ISO date string (YYYY-MM-DD)
}

/**
 * Get date range for preset options
 * Returns ISO date strings (YYYY-MM-DD format) for date-only comparisons
 */
export function getDateRange(preset: DatePreset): DateRange | null {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  
  switch (preset) {
    case 'all':
      return null; // No date filtering
    
    case 'today':
      return {
        start: today.toISOString().split('T')[0],
        end: today.toISOString().split('T')[0]
      };
    
    case 'last3days': {
      const start = new Date(today);
      start.setDate(start.getDate() - 2); // Including today
      return {
        start: start.toISOString().split('T')[0],
        end: today.toISOString().split('T')[0]
      };
    }
    
    case 'last7days': {
      const start = new Date(today);
      start.setDate(start.getDate() - 6); // Including today
      return {
        start: start.toISOString().split('T')[0],
        end: today.toISOString().split('T')[0]
      };
    }
    
    case 'thisweek': {
      const start = new Date(today);
      const dayOfWeek = start.getDay();
      const diff = dayOfWeek === 0 ? -6 : 1 - dayOfWeek; // Monday as start of week
      start.setDate(start.getDate() + diff);
      return {
        start: start.toISOString().split('T')[0],
        end: today.toISOString().split('T')[0]
      };
    }
    
    case 'thismonth': {
      const start = new Date(today.getFullYear(), today.getMonth(), 1);
      return {
        start: start.toISOString().split('T')[0],
        end: today.toISOString().split('T')[0]
      };
    }
    
    case 'thisyear': {
      const start = new Date(today.getFullYear(), 0, 1);
      return {
        start: start.toISOString().split('T')[0],
        end: today.toISOString().split('T')[0]
      };
    }
    
    case 'custom':
      return null; // User will manually set dates
    
    default:
      return null;
  }
}

/**
 * Get display label for date preset
 */
export function getPresetLabel(preset: DatePreset): string {
  const labels: Record<DatePreset, string> = {
    all: 'All Time',
    today: 'Today',
    last3days: 'Last 3 Days',
    last7days: 'Last 7 Days',
    thisweek: 'This Week',
    thismonth: 'This Month',
    thisyear: 'This Year',
    custom: 'Custom Range'
  };
  return labels[preset] || 'All Time';
}

/**
 * Get all available preset options
 */
export function getPresetOptions(): { value: DatePreset; label: string }[] {
  return [
    { value: 'all', label: 'All Time' },
    { value: 'today', label: 'Today' },
    { value: 'last3days', label: 'Last 3 Days' },
    { value: 'last7days', label: 'Last 7 Days' },
    { value: 'thisweek', label: 'This Week' },
    { value: 'thismonth', label: 'This Month' },
    { value: 'thisyear', label: 'This Year' },
    { value: 'custom', label: 'Custom Range' }
  ];
}
