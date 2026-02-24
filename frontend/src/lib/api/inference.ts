/**
 * Unified Inference API Client
 * Model-agnostic inference supporting YOLO, SAM3, and future models
 */

import client from './client';
import type { 
  PredictionJob, 
  PredictionResponse, 
  PredictionResult, 
  PredictionResponseWithFrame,
  PredictionSummary,
  InferencePrompt,
  InferenceConfig,
  InferenceCapabilities,
  ValidationResult,
  ModelInfo
} from '@/lib/types';

// Base endpoint for all inference operations
const INFERENCE_ENDPOINT = '/inference';

/**
 * Helper function to append InferenceConfig fields to FormData
 * @param formData - The FormData instance to append to
 * @param config - The InferenceConfig to extract fields from
 * @param options - Optional fields to include/exclude
 */
function appendInferenceConfigToFormData(
    formData: FormData,
    config: InferenceConfig,
    options?: {
        includeModelId?: boolean;
        includeConfidence?: boolean;
        includeCampaignId?: boolean;
        includeClassFilter?: boolean;
        includePrompts?: boolean;
        includeVideoProperties?: boolean;
    }
): void {
    const {
        includeModelId = true,
        includeConfidence = true,
        includeCampaignId = true,
        includeClassFilter = true,
        includePrompts = true,
        includeVideoProperties = false
    } = options || {};

    if (includeModelId && config.modelId) {
        formData.append('model_id', config.modelId.toString());
    }

    if (includeConfidence && config.confidence !== undefined) {
        formData.append('confidence', config.confidence.toString());
    }

    if (includeCampaignId && config.campaignId) {
        formData.append('campaign_id', config.campaignId.toString());
    }

    if (includeClassFilter && config.classFilter && config.classFilter.length > 0) {
        formData.append('class_filter', config.classFilter.join(','));
    }

    if (includePrompts && config.prompts) {
        formData.append('prompts', JSON.stringify(config.prompts));
    }

    if (includeVideoProperties) {
        if (config.duration !== undefined) {
            formData.append('video_duration', config.duration.toString());
        }
        if (config.fps !== undefined) {
            formData.append('video_fps', config.fps.toString());
        }
    }

    if (config.imgsz !== undefined) {
        formData.append('imgsz', config.imgsz.toString());
    }

    if (config.iouThreshold !== undefined) {
        formData.append('iou_threshold', config.iouThreshold.toString());
    }
}

export const InferenceAPI = {
    /**
     * Run inference on a single image.
     * Automatically routes to appropriate model service (YOLO, SAM3, etc.).
     */
    async inferSingle(file: File, config: InferenceConfig): Promise<PredictionResponse> {
        const formData = new FormData();
        formData.append('file', file);
        appendInferenceConfigToFormData(formData, config);

        const response = await client.post<PredictionResponse>(`${INFERENCE_ENDPOINT}/single`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
        });
        return response.data;
    },

    /**
     * Run inference for preview only - no database records created.
     * Used for live preview in video manual capture mode.
     */
    async inferPreview(file: File, config: InferenceConfig): Promise<PredictionResponse> {
        const formData = new FormData();
        formData.append('file', file);
        appendInferenceConfigToFormData(formData, config, { includeCampaignId: false });

        const response = await client.post<PredictionResponse>(`${INFERENCE_ENDPOINT}/preview`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
        });
        return response.data;
    },

    /**
     * Run inference on multiple images.
     * Background worker processes images asynchronously.
     */
    async inferBatch(files: File[], config: InferenceConfig): Promise<PredictionJob> {
        const formData = new FormData();
        appendInferenceConfigToFormData(formData, config);
        
        files.forEach((file) => {
            formData.append('files', file);
        });

        const response = await client.post<PredictionJob>(`${INFERENCE_ENDPOINT}/batch`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },

    /**
     * Run inference on a video file.
     * Background worker processes frames asynchronously.
     */
    async inferVideo(
        file: File,
        config: InferenceConfig,
        captureMode: 'continuous' | 'manual' = 'manual',
        skipFrames = 5,
        limitFrames?: number
    ): Promise<PredictionJob> {
        const formData = new FormData();
        appendInferenceConfigToFormData(formData, config, { includeVideoProperties: true });
        
        if (limitFrames) {
            formData.append('limit_frames', limitFrames.toString());
        }

        formData.append('skip_frames', skipFrames.toString());
        formData.append('capture_mode', captureMode);
        formData.append('file', file);

        const response = await client.post<PredictionJob>(`${INFERENCE_ENDPOINT}/video`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
        });
        return response.data;
    },

    // Video Capture a single frame for manual mode 
    // START WITH MANUAL JOB (startManualJob) FIRST
    async video_capture_frame(
        jobId: number,
        frameFile: File,
        config: InferenceConfig,
        frameNumber?: number,
        frameTimestamp?: string, 
    ): Promise<PredictionResponse> {
        const formData = new FormData();
        formData.append('file', frameFile);
        if (frameNumber !== undefined) formData.append('frame_number', frameNumber.toString());
        if (frameTimestamp) formData.append('frame_timestamp', frameTimestamp);

        appendInferenceConfigToFormData(formData, config, { 
            includeModelId: false, 
            includeCampaignId: false 
        });
    
        const response = await client.post<PredictionResponse>(`${INFERENCE_ENDPOINT}/video/${jobId}/capture`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },

    // RTSP Stream Methods
    async inferRTSP(
        rtspUrl: string,
        config: InferenceConfig,
        captureMode: 'continuous' | 'manual' = 'manual',
        skipFrames: number = 10,
    ): Promise<PredictionJob> {
        const formData = new FormData();
        appendInferenceConfigToFormData(formData, config);
        
        formData.append('rtsp_url', rtspUrl);
        formData.append('capture_mode', captureMode);
        formData.append('skip_frames', skipFrames.toString());

        const response = await client.post<PredictionJob>(`${INFERENCE_ENDPOINT}/rtsp`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },

    // RTSP Capture a single frame for manual mode
    async rtsp_capture_frame(jobId: number, config: InferenceConfig): Promise<PredictionResult> {
        const formData = new FormData();
        // Only prompts can be updated during manual capture
        appendInferenceConfigToFormData(formData, config, {
            includeModelId: false,
            includeConfidence: false,
            includeCampaignId: false,
            includeClassFilter: false,
        });

        const response = await client.post<PredictionResult>(`${INFERENCE_ENDPOINT}/rtsp/${jobId}/capture`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },

    // RTSP Get latest frame and predictions
    async rtsp_get_latest_frame(jobId: number): Promise<PredictionResponseWithFrame> {
        const response = await client.get<{ frame: string; predictions: PredictionResponse }>(`${INFERENCE_ENDPOINT}/rtsp/${jobId}/latest-frame`);
        return response.data;
    },

    // Webcam Stream Methods
    async inferWebcam(
        config: InferenceConfig,
        captureMode: 'continuous' | 'manual' = 'manual',
    ): Promise<PredictionJob> {
        const formData = new FormData();
        appendInferenceConfigToFormData(formData, config);
        
        formData.append('capture_mode', captureMode);

        const response = await client.post<PredictionJob>(`${INFERENCE_ENDPOINT}/webcam`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },

    // Webcam Capture a single frame for manual mode
    async webcam_capture_frame(
        jobId: number,
        frameFile: File,
        config: InferenceConfig,
        frameNumber?: number,
    ): Promise<PredictionResponse> {
        const formData = new FormData();
        formData.append('file', frameFile);
        if (frameNumber !== undefined) formData.append('frame_number', frameNumber.toString());

        appendInferenceConfigToFormData(formData, config, { 
            includeModelId: false, 
            includeCampaignId: false 
        });
    
        const response = await client.post<PredictionResponse>(`${INFERENCE_ENDPOINT}/webcam/${jobId}/capture`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },

    async getJob(id: number): Promise<PredictionJob> {
        const response = await client.get<PredictionJob>(`${INFERENCE_ENDPOINT}/jobs/${id}`);
        return response.data;
    },

    async getJobs(
        skip = 0,
        limit = 100,
        filters?: {
        modelId?: number;
        datasetId?: number;
        status?: string;
        mode?: string;
        taskType?: string;
        startDate?: string;
        endDate?: string;
        search?: string;
        sortBy?: string;
        sortOrder?: 'asc' | 'desc';
        }
    ): Promise<{ jobs: PredictionJob[]; total: number; skip: number; limit: number }> {
        const params: any = { skip, limit };
        if (filters?.modelId) params.model_id = filters.modelId;
        if (filters?.datasetId) params.dataset_id = filters.datasetId;
        if (filters?.status) params.status = filters.status;
        if (filters?.mode) params.mode = filters.mode;
        if (filters?.taskType) params.task_type = filters.taskType;
        if (filters?.startDate) params.start_date = filters.startDate;
        if (filters?.endDate) params.end_date = filters.endDate;
        if (filters?.search) params.search = filters.search;
        if (filters?.sortBy) params.sort_by = filters.sortBy;
        if (filters?.sortOrder) params.sort_order = filters.sortOrder;
    
        const response = await client.get<{ jobs: PredictionJob[]; total: number; skip: number; limit: number }>(`${INFERENCE_ENDPOINT}/jobs`, { params });
        return response.data;
    },

    async getResults(jobId: number, skip = 0, limit = 100): Promise<PredictionResult[]> {
        const response = await client.get<PredictionResult[]>(`${INFERENCE_ENDPOINT}/jobs/${jobId}/results`, {
            params: { skip, limit },
        });
        return response.data;
    },

    /**
     * Get inference result image (with overlays).
     */
    async getResultImage(result_id: number): Promise<any> {
        const response = await client.get(`${INFERENCE_ENDPOINT}/results/${result_id}/image`, {
            responseType: 'blob'
        });
        return response;
    },

    async stopJob(jobId: number): Promise<PredictionJob> {
        const response = await client.post<PredictionJob>(`${INFERENCE_ENDPOINT}/jobs/${jobId}/stop`);
        return response.data;
    },

    async cancelJob(jobId: number): Promise<PredictionJob> {
        const response = await client.post<PredictionJob>(`${INFERENCE_ENDPOINT}/jobs/${jobId}/cancel`);
        return response.data;
    },

    /**
     * Start a manual inference job (for live capture). DEPRECATED.
     */
    async startManualJob(
        filename: string,
        config: InferenceConfig,
        source_type?: string,
        mode?: string,
    ): Promise<PredictionJob> {
        throw new Error("This method is deprecated. Use InferenceAPI.inferVideo, InferenceAPI.inferRTSP, or InferenceAPI.inferWebcam instead.");
        // const formData = new FormData();
        // formData.append('filename', filename);
        
        // appendInferenceConfigToFormData(formData, config, { includeVideoProperties: true });

        // if (source_type) {
        //     formData.append('source_type', source_type);
        // }

        // if (mode) {
        //     formData.append('mode', mode);
        // }
    
        // const response = await client.post<PredictionJob>(`${INFERENCE_ENDPOINT}/jobs/start`, formData, {
        //     headers: {
        //         'Content-Type': 'multipart/form-data',
        //     },
        // });
        // return response.data;
    },

    async sendJobHeartbeat(jobId: number): Promise<{ status: string; job_id: number; last_activity: string | null }> {
        const response = await client.post<{ status: string; job_id: number; last_activity: string | null }>(
            `${INFERENCE_ENDPOINT}/jobs/${jobId}/heartbeat`
        );
        return response.data;
    },

    /**
     * Get list of available inference models.
     */
    async listModels(inference_type?: string, task_type?: string): Promise<ModelInfo[]> {
        const params: any = {};
        if (inference_type) {
            params.inference_type = inference_type;
        }
        if (task_type) {
            params.task_type = task_type;
        }
        const response = await client.get<ModelInfo[]>(`${INFERENCE_ENDPOINT}/models`, { params });
        return response.data;
    },

    /**
     * Get inference service capabilities and supported model types.
     */
    async getCapabilities(): Promise<InferenceCapabilities> {
        const response = await client.get<InferenceCapabilities>(`${INFERENCE_ENDPOINT}/capabilities`);
        return response.data;
    },

    /**
     * Validate inference configuration before running.
     */
    async validateConfig(
        modelId: number,
        taskType?: string,
        prompts?: InferencePrompt[]
    ): Promise<ValidationResult> {
        const formData = new FormData();
        const config: InferenceConfig = { modelId, prompts };
        appendInferenceConfigToFormData(formData, config, {  includeVideoProperties: true });
        
        if (taskType) {
            formData.append('task_type', taskType);
        }

        const response = await client.post<ValidationResult>(`${INFERENCE_ENDPOINT}/validate`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
        });
        return response.data;
    },

    async getStats(): Promise<PredictionSummary> {
        const response = await client.get<PredictionSummary>(`${INFERENCE_ENDPOINT}/jobs/stats`);
        return response.data;
    },

    // Export methods
    async exportImages(
        jobId: number,
        options: { annotated: boolean; resultIds?: number[] }
    ): Promise<{ export_job_id: number; status: string }> {
        const params: any = { annotated: options.annotated };
        if (options.resultIds && options.resultIds.length > 0) {
            params.result_ids = options.resultIds.join(',');
        }
        const response = await client.post(`${INFERENCE_ENDPOINT}/jobs/${jobId}/export/images`, null, { params });
        return response.data;
    },
    
    async exportData(
        jobId: number,
        options: { format: 'json' | 'csv'; resultIds?: number[] }
    ): Promise<{ export_job_id: number; status: string }> {
        const params: any = { format: options.format };
        if (options.resultIds && options.resultIds.length > 0) {
            params.result_ids = options.resultIds.join(',');
        }
        const response = await client.post(`${INFERENCE_ENDPOINT}/jobs/${jobId}/export/data`, null, { params });
        return response.data;
    },
    
    async exportPDF(
        jobId: number,
        options: { resultIds?: number[] }
    ): Promise<{ export_job_id: number; status: string }> {
        const params: any = {};
        if (options.resultIds && options.resultIds.length > 0) {
            params.result_ids = options.resultIds.join(',');
        }
        const response = await client.post(`${INFERENCE_ENDPOINT}/jobs/${jobId}/export/pdf`, null, { params });
        return response.data;
    },
    
    async getExportStatus(jobId: number, exportId: number): Promise<any> {
        const response = await client.get(`${INFERENCE_ENDPOINT}/jobs/${jobId}/export/${exportId}/status`);
        return response.data;
    },
    
    async downloadExport(jobId: number, exportId: number): Promise<void> {
        const response = await client.get(`${INFERENCE_ENDPOINT}/jobs/${jobId}/export/${exportId}/download`, {
            responseType: 'blob',
        });
        
        // Trigger download
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        
        // Extract filename from Content-Disposition header if available
        const contentDisposition = response.headers['content-disposition'];
        let filename = `export_${exportId}.zip`;
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i);
            if (filenameMatch) {
                filename = filenameMatch[1];
            }
        }
        
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
    },

    async exportSingleResultPDF(resultId: number): Promise<{ export_job_id: number; status: string; result_id: number }> {
        const response = await client.post(`${INFERENCE_ENDPOINT}/results/${resultId}/export/pdf`);
        return response.data;
    },
};

export default InferenceAPI;
