/**
 * Datasets API
 */
import client from './client';
import type { Dataset, DatasetDetail, DatasetFilesResponse, ImageUploadResult, FileDeleteResult, ImageLabelData, BoundingBox } from '@/lib/types';

export const datasetsAPI = {
  async list(skip = 0, limit = 100, dataset_id?: number): Promise<Dataset[]> {
    const params: any = { skip, limit };
    if (dataset_id !== undefined) {
      params.dataset_id = dataset_id;
    }
    const response = await client.get<Dataset[]>('/datasets', {
      params,
    });
    return response.data;
  },

  // Convenience method alias
  async listDatasets(skip = 0, limit = 100, dataset_id?: number): Promise<Dataset[]> {
    return this.list(skip, limit, dataset_id);
  },

  async get(id: number): Promise<DatasetDetail> {
    const response = await client.get<DatasetDetail>(`/datasets/${id}`);
    return response.data;
  },

  async create(name: string, file: File, description?: string, taskType = 'detect'): Promise<Dataset> {
    const formData = new FormData();
    formData.append('name', name);
    formData.append('file', file);
    if (description) {
      formData.append('description', description);
    }
    formData.append('task_type', taskType);

    const response = await client.post<Dataset>('/datasets', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async createEmpty(name: string, description?: string, taskType = 'detect'): Promise<Dataset> {
    const formData = new FormData();
    formData.append('name', name);
    if (description) {
      formData.append('description', description);
    }
    formData.append('task_type', taskType);

    const response = await client.post<Dataset>('/datasets/empty', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async update(
    id: number, 
    updates: {
      name?: string;
      description?: string;
      classes_json?: { [key: string]: string };
      file?: File;
    }
  ): Promise<DatasetDetail> {
    const formData = new FormData();
    
    if (updates.name) {
      formData.append('name', updates.name);
    }
    if (updates.description !== undefined) {
      formData.append('description', updates.description);
    }
    if (updates.classes_json) {
      formData.append('classes_json', JSON.stringify(updates.classes_json));
    }
    if (updates.file) {
      formData.append('file', updates.file);
    }

    const response = await client.put<DatasetDetail>(`/datasets/${id}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async delete(id: number): Promise<void> {
    await client.delete(`/datasets/${id}`);
  },

  async listFiles(
    id: number,
    split: string = 'train',
    className?: string,
    limit: number = 50,
    skip: number = 0,
    search?: string,
    sortBy: string = 'name_asc',
    labelFilter: string = 'all'
  ): Promise<DatasetFilesResponse> {
    const response = await client.get<DatasetFilesResponse>(`/datasets/${id}/files`, {
      params: { 
        split, 
        class_name: className, 
        limit, 
        skip,
        search,
        sort_by: sortBy,
        label_filter: labelFilter
      },
    });
    return response.data;
  },

  getImageUrl(id: number, filepath: string): string {
    return `/api/datasets/${id}/image/${filepath}`;
  },

  async uploadImages(
    id: number,
    files: File[],
    split: string,
    className?: string
  ): Promise<ImageUploadResult> {
    const formData = new FormData();
    formData.append('split', split);
    if (className) {
      formData.append('class_name', className);
    }
    files.forEach(file => {
      formData.append('files', file);
    });

    const response = await client.post<ImageUploadResult>(`/datasets/${id}/upload-images`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async deleteFile(id: number, filepath: string): Promise<FileDeleteResult> {
    const response = await client.delete<FileDeleteResult>(`/datasets/${id}/files/${filepath}`);
    return response.data;
  },

  async recalculateStats(id: number): Promise<{
    id: number;
    images_count: number;
    labels_count: number;
    status: string;
    message: string;
  }> {
    const response = await client.post(`/datasets/${id}/recalculate`);
    return response.data;
  },

  async getImageLabels(id: number, imagePath: string): Promise<ImageLabelData> {
    const response = await client.get<ImageLabelData>(`/datasets/${id}/label/${imagePath}`);
    return response.data;
  },

  async saveImageLabels(
    id: number,
    imagePath: string,
    boxes: BoundingBox[],
    deleteLabel: boolean = true
  ): Promise<{ success: boolean; message: string; boxes_saved: number }> {
    const response = await client.post(`/datasets/${id}/label/${imagePath}`, boxes, {
      params: { delete_label: deleteLabel },
    });
    return response.data;
  },

  async saveSegmentationLabels(
    id: number,
    imagePath: string,
    polygons: Array<{ class_id: number; points: number[] }>,
    deleteLabel: boolean = true
  ): Promise<{ success: boolean; message: string; polygons_saved: number }> {
    const response = await client.post(
      `/datasets/${id}/label/${imagePath}/segmentation`,
      { polygons }, // Wrap polygons in an object
      {
        params: { delete_label: deleteLabel },
      }
    );
    return response.data;
  },

  async validate(id: number): Promise<any> {
    const response = await client.post(`/datasets/${id}/validate`);
    return response.data;
  },

  async rescanClasses(
    id: number,
    splits: string[] = ['train', 'val', 'test']
  ): Promise<{
    success: boolean;
    message: string;
    scanned_splits: string[];
    discovered_classes: string[];
    new_classes: Array<{ id: string; name: string }>;
    total_classes: number;
  }> {
    const response = await client.post(`/datasets/${id}/rescan-classes`, null, {
      params: { splits },
    });
    return response.data;
  },

  async distributeImages(
    id: number,
    seed?: number
  ): Promise<import('../../types').DistributionResult> {
    const params: any = {};
    if (seed !== undefined && seed !== null) {
      params.seed = seed;
    }
    const response = await client.post(`/datasets/${id}/distribute`, null, {
      params,
    });
    return response.data;
  },
};
