/**
 * Models API
 */
import client from './client';
import type { BaseModelInfo, Model, ModelDetail } from '@/lib/types';

export const modelsAPI = {
  async listBase(): Promise<BaseModelInfo[]> {
    const response = await client.get<BaseModelInfo[]>('/models/base');
    return response.data;
  },

  async list(skip = 0, limit = 100, projectId?: number, taskType?: string): Promise<Model[]> {
    const response = await client.get<Model[]>('/models', {
      params: { skip, limit, project_id: projectId, task_type: taskType },
    });
    return response.data;
  },

  // Convenience method alias
  async listModels(skip = 0, limit = 100, projectId?: number, taskType?: string): Promise<Model[]> {
    return this.list(skip, limit, projectId, taskType);
  },

  async get(id: number): Promise<ModelDetail> {
    const response = await client.get<ModelDetail>(`/models/${id}`);
    return response.data;
  },

  async create(name: string, baseType: string, projectId: number): Promise<Model> {
    const response = await client.post<Model>('/models', {
      name,
      base_type: baseType,
      project_id: projectId,
    });
    return response.data;
  },

  async delete(id: number): Promise<void> {
    await client.delete(`/models/${id}`);
  },

  async upload(projectId: number, name: string, baseType: string, file: File, taskType?: string | null, bpeFile?: File | null): Promise<Model> {
    const formData = new FormData();
    formData.append('project_id', projectId.toString());
    formData.append('name', name);
    formData.append('base_type', baseType);
    formData.append('file', file);
    
    if (taskType) {
      formData.append('task_type', taskType);
    }
    
    if (bpeFile) {
      formData.append('bpe_file', bpeFile);
    }

    const response = await client.post<Model>('/models/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  async validate(id: number): Promise<Model> {
    const response = await client.post<Model>(`/models/${id}/validate`);
    return response.data;
  },

  async update(id: number, name: string, description?: string | null, tags?: string | null): Promise<Model> {
    const response = await client.put<Model>(`/models/${id}`, { 
      name,
      description: description !== undefined ? description : undefined,
      tags: tags !== undefined ? tags : undefined
    });
    return response.data;
  },
};
