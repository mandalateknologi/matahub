/**
 * Files API Client
 * Handles file management operations for user storage
 */
import { apiClient } from './client';
import type {
  FileItem,
  FolderTree,
  StorageStats,
  FileUploadResponse,
  FolderCreateRequest,
  FolderCreateResponse,
  MigrationStats,
  SyncResult
} from '@/lib/types/files';

/**
 * Files API class
 */
class FilesAPI {
  private client = apiClient.getClient();

  /**
   * List user's files
   */
  async listFiles(folderPath?: string, includeDeleted: boolean = false): Promise<FileItem[]> {
    const params: any = {};
    if (folderPath !== undefined) {
      params.folder_path = folderPath;
    }
    if (includeDeleted) {
      params.include_deleted = true;
    }

    const response = await this.client.get<FileItem[]>('/files/', { params });
    return response.data;
  }

  /**
   * Get folder tree structure
   */
  async getFolderTree(): Promise<FolderTree> {
    const response = await this.client.get<FolderTree>('/files/tree/');
    return response.data;
  }

  /**
   * Get storage statistics
   */
  async getStorageStats(): Promise<StorageStats> {
    const response = await this.client.get<StorageStats>('/files/storage-stats/');
    return response.data;
  }

  /**
   * Upload a file
   */
  async uploadFile(file: File, folderPath: string = 'shared'): Promise<FileUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await this.client.post<FileUploadResponse>(
      `/files/upload/?folder_path=${encodeURIComponent(folderPath)}`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  }

  /**
   * Create a new folder
   */
  async createFolder(request: FolderCreateRequest): Promise<FolderCreateResponse> {
    const response = await this.client.post<FolderCreateResponse>('/files/folders/', request);
    return response.data;
  }

  /**
   * Delete a file (move to trash)
   */
  async deleteFile(fileId: number): Promise<{ message: string }> {
    const response = await this.client.delete(`/files/${fileId}/`);
    return response.data;
  }

  /**
   * Permanently delete a file from trash
   */
  async permanentDeleteFile(fileId: number): Promise<{ message: string }> {
    const response = await this.client.delete(`/files/${fileId}/permanent/`);
    return response.data;
  }

  /**
   * Restore a file from trash
   */
  async restoreFile(fileId: number, restoreFolder: string = 'shared'): Promise<{ message: string; file: FileItem }> {
    const response = await this.client.post(`/files/${fileId}/restore/`, null, {
      params: { restore_folder: restoreFolder },
    });
    return response.data;
  }

  /**
   * Download a file
   */
  async downloadFile(fileId: number, filename: string): Promise<void> {
    const response = await this.client.get(`/files/${fileId}/download/`, {
      responseType: 'blob',
    });

    // Create download link
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  }

  /**
   * Get preview URL for a file
   */
  getPreviewUrl(fileId: number): string {
    // Get base URL and token from localStorage
    const baseURL = this.client.defaults.baseURL || '';
    const token = localStorage.getItem('access_token') || '';
    return `${baseURL}/files/${fileId}/preview/?token=${encodeURIComponent(token)}`;
  }

  /**
   * Migrate existing files
   */
  async migrateExistingFiles(): Promise<MigrationStats> {
    const response = await this.client.post<MigrationStats>('/files/migrate/');
    return response.data;
  }

  /**
   * Sync files from DATA_DIR (alias for migrateExistingFiles)
   */
  async syncFiles(): Promise<SyncResult> {
    const stats = await this.migrateExistingFiles();
    return {
      added: stats.files_migrated,
      skipped: stats.files_skipped,
      failed: 0 // Backend doesn't track failed, only found/migrated/skipped
    };
  }

  /**
   * Move file to new folder
   */
  async moveFile(fileId: number, newFolderPath: string): Promise<FileItem> {
    const response = await this.client.put<FileItem>(`/files/${fileId}/move/`, {
      new_folder_path: newFolderPath,
    });
    return response.data;
  }

  /**
   * Rename file
   */
  async renameFile(fileId: number, newName: string): Promise<FileItem> {
    const response = await this.client.put<FileItem>(`/files/${fileId}/rename/`, {
      new_name: newName,
    });
    return response.data;
  }

  /**
   * Batch delete files (move to trash)
   */
  async batchDeleteFiles(fileIds: number[]): Promise<{ success: number; failed: number; errors: any[] }> {
    const response = await this.client.post('/files/batch-delete/', {
      file_ids: fileIds,
    });
    return response.data;
  }

  /**
   * Batch restore files from trash
   */
  async batchRestoreFiles(fileIds: number[], restoreTo: string = 'shared'): Promise<{ success: number; failed: number; errors: any[] }> {
    const response = await this.client.post('/files/batch-restore/', {
      file_ids: fileIds,
      restore_to: restoreTo,
    });
    return response.data;
  }

  /**
   * Format file size to human-readable format
   */
  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  }

  /**
   * Get file icon based on type
   */
  getFileIcon(type: string): string {
    switch (type) {
      case 'image':
        return '🖼️';
      case 'video':
        return '🎥';
      case 'folder':
        return '📁';
      default:
        return '📄';
    }
  }
}

export const filesAPI = new FilesAPI();
