/**
 * Frontend configuration
 */
export const config = {
  // Polling intervals (in milliseconds)
  WORKFLOW_POLL_INTERVAL: 3000, // 3 seconds
  TRAINING_POLL_INTERVAL: 2000, // 2 seconds
  DETECTION_POLL_INTERVAL: 2000, // 2 seconds
  
  // API configuration
  API_BASE_URL: '/api',
  
  // Chart colors
  CHART_COLORS: {
    primary: '#1D2F43',
    accent: '#E1604C',
    success: '#28a745',
    warning: '#ffc107',
    danger: '#dc3545',
    info: '#17a2b8'
  }
};
