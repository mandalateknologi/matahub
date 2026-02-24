/**
 * Dataset Types
 */

export interface Dataset {
  id: number;
  name: string;
  description?: string;
  task_type: string;
  status: 'empty' | 'incomplete' | 'valid';
  images_count: number;
  labels_count: number;
  classes_json: { [key: string]: string };  // Dict mapping class IDs to names
  created_at: string;
}

export interface DatasetDetail extends Dataset {
  yaml_path?: string;
}

export interface DatasetFile {
  name: string;
  path: string;
  size: number;
  split: string;
  class_name?: string;
}

export interface DatasetFilesResponse {
  files: DatasetFile[];
  total: number;
  has_more: boolean;
  split: string;
  class_name?: string;
  classes?: string[];
}

export interface ImageUploadResult {
  uploaded: Array<{
    filename: string;
    saved_as: string;
    size: number;
  }>;
  errors: Array<{
    filename: string;
    error: string;
  }>;
  total_uploaded: number;
  total_errors: number;
}

export interface FileDeleteResult {
  deleted: boolean;
  filepath: string;
  warnings: string[];
}

export interface DistributionResult {
  success: boolean;
  message: string;
  distribution: {
    train: number;
    val: number;
    test: number;
  };
  percentages?: {
    train: number;
    val: number;
    test: number;
  };
  warnings?: string[];
  already_optimal?: boolean;
  current_distribution?: {
    train: number;
    val: number;
    test: number;
  };
  current_ratios?: {
    train: number;
    val: number;
    test: number;
  };
  classes_processed?: number;
}

// Label Types (for Detection Bounding Boxes)
export interface BoundingBox {
  class_id: number;
  x_center: number;
  y_center: number;
  width: number;
  height: number;
}

export interface ImageLabelData {
  image_width: number;
  image_height: number;
  task_type?: string;
  boxes?: BoundingBox[];
  polygons?: Array<{ class_id: number; points: number[] }>;
  classes: { [key: string]: string };
}

export interface SaveLabelsRequest {
  boxes: BoundingBox[];
}
