/**
 * Recognition Catalog Types
 * TypeScript interfaces for recognition catalogs, labels, images, and similarity search
 */

export interface RecognitionCatalog {
  id: number;
  name: string;
  description?: string;
  category: string;
  image_count: number;
  label_count: number;
  creator_id: number;
  created_at: string;
  updated_at: string;
}

export interface RecognitionCatalogDetail extends RecognitionCatalog {
  labels: RecognitionLabel[];
}

export interface RecognitionCatalogCreate {
  name: string;
  description?: string;
  category: string;
}

export interface RecognitionCatalogUpdate {
  name?: string;
  description?: string;
  category?: string;
}

export interface RecognitionLabel {
  id: number;
  catalog_id: number;
  label_name: string;
  description?: string;
  image_count: number;
  created_at: string;
  updated_at: string;
}

export interface RecognitionLabelDetail extends RecognitionLabel {
  images: RecognitionImage[];
}

export interface RecognitionLabelCreate {
  label_name: string;
  description?: string;
}

export interface RecognitionLabelUpdate {
  label_name?: string;
  description?: string;
}

export interface RecognitionImage {
  id: number;
  label_id: number;
  image_path: string;
  thumbnail_path?: string;
  is_processed: boolean;
  created_at: string;
}

export interface RecognitionImageDetail extends RecognitionImage {
  embedding?: number[]; // 512-dimensional CLIP embedding
}

export interface RecognitionJob {
  id: number;
  catalog_id: number;
  label_id?: number;
  total_images: number;
  processed_images: number;
  failed_images: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export interface SimilaritySearchRequest {
  top_k?: number; // Default: 5
  threshold?: number; // Default: 0.5
  label_filter?: number[]; // Filter by specific label IDs
}

export interface SimilarityMatch {
  label_id: number;
  label_name: string;
  image_id: number;
  image_path: string;
  thumbnail_path?: string;
  similarity_score: number;
  distance_metric: string;
}

export interface SimilaritySearchResponse {
  query_image_path: string;
  matches: SimilarityMatch[];
  inference_time_ms: number;
  total_candidates: number;
}

export interface RecognitionCatalogStats {
  catalog_id: number;
  catalog_name: string;
  category: string;
  total_labels: number;
  total_images: number;
  processed_images: number;
  unprocessed_images: number;
  average_images_per_label: number;
}
