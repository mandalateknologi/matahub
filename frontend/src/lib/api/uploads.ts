/**
 * Uploads API Client
 * Handles file uploads for workflows
 */

import { apiClient } from "./client";
import type { FileUploadResponse, FileDeleteResponse } from "@/lib/types/files";

class UploadsAPI {
  /**
   * Upload file for workflow
   */
  async uploadWorkflowFile(
    workflowId: number,
    file: File
  ): Promise<FileUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);

    const response = await apiClient.getClient().post<FileUploadResponse>(
      `/uploads/workflows/${workflowId}/upload`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );

    return response.data;
  }

  /**
   * Delete specific workflow file
   */
  async deleteWorkflowFile(
    workflowId: number,
    filePath: string
  ): Promise<FileDeleteResponse> {
    const response = await apiClient.getClient().delete<FileDeleteResponse>(
      `/uploads/workflows/${workflowId}/file`,
      {
        params: { file_path: filePath },
      }
    );

    return response.data;
  }

  /**
   * Delete all workflow files
   */
  async deleteAllWorkflowFiles(
    workflowId: number
  ): Promise<FileDeleteResponse> {
    const response = await apiClient.getClient().delete<FileDeleteResponse>(
      `/uploads/workflows/${workflowId}/all`
    );

    return response.data;
  }
}

export const uploadsAPI = new UploadsAPI();
