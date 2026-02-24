/**
 * Centralized error messages for the capture page
 * Used for consistent error handling across all inference modes
 */

export interface ErrorMessage {
  title: string;
  message: string;
}

export const MODEL_ERRORS = {
  NO_MODEL_SELECTED: {
    title: "Model Required",
    message: "Please select a model first",
  },
  MODEL_NOT_FOUND: {
    title: "Model Not Found",
    message: "The selected model could not be found",
  },
} as const;

export const VALIDATION_ERRORS = {
  NO_FILE_SELECTED: {
    title: "Input Required",
    message: "Please select a file to proceed!",
  },
  NO_FILE: {
    title: "Input Required",
    message: "Please select a file to proceed!",
  },
  NO_FILES_SELECTED: {
    title: "Input Required",
    message: "Please select at least one file to proceed!",
  },
  NO_RTSP_URL: {
    title: "Input Required",
    message: "Please provide a valid RTSP URL!",
  },
  PROMPTS_REQUIRED: {
    title: "Prompts Required",
    message: "Please add at least one {promptMode} prompt for this model.",
  },
  PROMPTS_REQUIRED_AUTO: {
    title: "Prompts Required",
    message: "This model requires at least one prompt. Please add a text, point, or box prompt.",
  },
  PROMPTS_REQUIRED_VIDEO: {
    title: "Prompts Required",
    message: "Model that requires prompts requires at least one prompt. Please add a text, point, or box prompt before starting video detection.",
  },
  PROMPTS_REQUIRED_RTSP: {
    title: "Prompt Required",
    message: 'This model requires at least one prompt.\n\nPlease add a text prompt before starting RTSP detection.\nExample: "person", "car", "white bicycle"',
  },
  PROMPTS_REQUIRED_WEBCAM_CONTINUOUS: {
    title: "Prompt Required",
    message: "Continuous mode requires at least one prompt for this model. Please add a text, point, or box prompt.",
  },
} as const;

export const INFERENCE_ERRORS = {
  SINGLE_IMAGE_FAILED: {
    title: "Detection Error",
    message: "Single image detection failed. Please try again.",
  },
  BATCH_FAILED: {
    title: "Detection Error",
    message: "Batch processing failed. Please try again.",
  },
  VIDEO_FAILED: {
    title: "Detection Error",
    message: "Video detection failed. Please try again.",
  },
  VIDEO_JOB_START_FAILED: {
    title: "Video Job Error",
    message: "Failed to start video detection job. Please try again.",
  },
  VIDEO_JOB_FAILED: {
    title: "Video Job Error",
    message: "Video detection job failed. Please check the video file and try again.",
  },
  WEBCAM_FAILED: {
    title: "Detection Error",
    message: "Webcam detection failed. Please try again.",
  },
  RTSP_FAILED: {
    title: "Detection Error",
    message: "RTSP detection failed. Please try again.",
  },
  RTSP_JOB_START_FAILED: {
    title: "RTSP Job Error",
    message: "Failed to start RTSP detection job. Please try again.",
  },
  RTSP_JOB_FAILED: {
    title: "RTSP Job Error",
    message: "RTSP detection job failed. Please check the stream URL and try again.",
  },
  DETECTION_FAILED: {
    title: "Detection Error",
    message: "Detection failed. Please try again.",
  },
  FRAME_CAPTURE_FAILED: {
    title: "Capture Error",
    message: "Failed to capture frame. Please try again.",
  },
} as const;

export const SESSION_ERRORS = {
  VIDEO_SESSION_START_FAILED: {
    title: "Video Session Error",
    message: "Failed to start video session. Please try again.",
  },
  VIDEO_SESSION_FINISH_FAILED: {
    title: "Video Session Error",
    message: "Failed to finish video session. Please try again.",
  },
  VIDEO_SESSION_CONTINUE_FAILED: {
    title: "Video Session Error",
    message: "Failed to continue video session. Please try again.",
  },
  VIDEO_JOB_CANCEL_FAILED: {
    title: "Video Job Error",
    message: "Failed to cancel video job. Please try again.",
  },
  NO_ACTIVE_SESSION: {
    title: "Session Error",
    message: "No active session found. Please start a session first.",
  },
  WEBCAM_SESSION_START_FAILED: {
    title: "Webcam Session Error",
    message: "Failed to start webcam session. Please try again.",
  },
  WEBCAM_SESSION_FINISH_FAILED: {
    title: "Webcam Session Error",
    message: "Failed to finish webcam session. Please try again.",
  },
  WEBCAM_ACCESS_FAILED: {
    title: "Webcam Access Error",
    message: "Failed to access webcam. Please check permissions.",
  },
  RTSP_SESSION_START_FAILED: {
    title: "RTSP Session Error",
    message: "Failed to start RTSP session. Please try again.",
  },
  RTSP_SESSION_FINISH_FAILED: {
    title: "RTSP Session Error",
    message: "Failed to finish RTSP session. Please try again.",
  },
  RTSP_STOP_FAILED: {
    title: "RTSP Error",
    message: "Failed to stop RTSP stream. Please try again.",
  },
} as const;

export const SUCCESS_MESSAGES = {
  VIDEO_COMPLETED: {
    title: "Video Job Completed",
    message: "Video processing completed. Total frames processed: {count}",
  },
} as const;

/**
 * Get error message with interpolation support
 * @param error - Error message object with title and message
 * @param interpolations - Object with values to interpolate into message
 * @returns Error message with interpolated values
 */
export function getErrorMessage(
  error: ErrorMessage,
  interpolations?: Record<string, string | number>
): ErrorMessage {
  if (!interpolations) {
    return error;
  }

  let message = error.message;
  for (const [key, value] of Object.entries(interpolations)) {
    message = message.replace(`{${key}}`, String(value));
  }

  return {
    title: error.title,
    message,
  };
}

/**
 * Get success message with interpolation support
 * @param success - Success message object with title and message
 * @param interpolations - Object with values to interpolate into message
 * @returns Success message with interpolated values
 */
export function getSuccessMessage(
  success: ErrorMessage,
  interpolations?: Record<string, string | number>
): ErrorMessage {
  return getErrorMessage(success, interpolations);
}
