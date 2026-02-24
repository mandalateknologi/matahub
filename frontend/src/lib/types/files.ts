/**
 * File item response
 */
export interface FileItem {
  id: number;
  name: string;
  type: string;  // "image", "video", "folder"
  size: number;  // bytes
  path: string;
  folder_path: string;
  is_system_folder: boolean;
  is_deleted: boolean;
  uploaded_at: string;
  deleted_at?: string;
}

/**
 * Folder tree node
 */
export interface FolderNode {
  files: Array<{
    id: number;
    name: string;
    type: string;
    size: number;
    path: string;
    uploaded_at: string;
  }>;
  subfolders: { [key: string]: FolderNode };
}

/**
 * Folder tree response
 */
export interface FolderTree {
  tree: {
    workflows: FolderNode;
    shared: FolderNode;
    trash: FolderNode;
  };
}

/**
 * Storage statistics
 */
export interface StorageStats {
  used_bytes: number;
  total_bytes: number;
  file_count: number;
  used_percentage: number;
}

/**
 * File upload response
 */
export interface FileUploadResponse {
  id: number;
  name: string;
  type: string;
  size: number;
  path: string;
  folder_path: string;
  uploaded_at: string;
  message: string;
}

/**
 * Folder create request
 */
export interface FolderCreateRequest {
  name: string;
  parent_path?: string;
}

/**
 * Folder create response
 */
export interface FolderCreateResponse {
  id: number;
  name: string;
  path: string;
  message: string;
}

/**
 * Migration statistics
 */
export interface MigrationStats {
  files_found: number;
  files_migrated: number;
  files_skipped: number;
  folders_migrated: number;
}

/**
 * Sync result (alias for migration stats)
 */
export interface SyncResult {
  added: number;
  skipped: number;
  failed: number;
}

export interface FileUploadResponse {
  file_path: string;
  filename: string;
  size: number;
  uploaded_at: string;
}

export interface FileDeleteResponse {
  success: boolean;
  message: string;
}
