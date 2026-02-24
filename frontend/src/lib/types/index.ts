/**
 * ATVISION TypeScript Definitions - Barrel Export
 * 
 * Central export point for all type definitions.
 * Import from '@/lib/types' to access all types.
 */

// User & Authentication
export type { UserRole, User, UserWithResourceCounts, LoginCredentials, Token, ApiKey, ApiKeyCreateResponse, ProfileUpdateRequest, ChangePasswordRequest, PasswordStrengthResponse } from './user';

// Dataset
export type { Dataset, DatasetDetail, DatasetFile, DatasetFilesResponse, ImageUploadResult, FileDeleteResult, DistributionResult, BoundingBox, ImageLabelData, SaveLabelsRequest } from './dataset';

// Project
export type { Project, ProjectDetail, DeleteConfirmation } from './project';

// Model
export type { BaseModelInfo, Model, ModelDetail, ModelInfo } from './model';

// Training
export type { TrainingJob, TrainingStart, TrainingSummary } from './training';

// Prediction/Inference
export type { PredictionJob, MaskData, ResultConfig, PredictionResult, PredictionResponse, DetectionData, GalleryPredictionResponse, GalleryImage, PredictionResponseWithFrame, InferencePrompt, InferenceConfig, InferenceCapabilities, ValidationResult } from './prediction';

// Reports & Analytics
export type { ClassificationMetrics, PredictionSummary } from './reports';

// Campaign (existing)
export type { Campaign, CampaignStats, CampaignExport, CampaignExportJob } from './campaign';

// Recognition (existing)
export type { RecognitionCatalog, RecognitionLabel, RecognitionLabelCreate, RecognitionLabelUpdate, RecognitionCatalogStats } from './recognition';

// Aggregate exports for convenience
export * from './user';
export * from './dataset';
export * from './project';
export * from './model';
export * from './training';
export * from './prediction';
export * from './reports';
export * from './campaign';
export * from './recognition';
