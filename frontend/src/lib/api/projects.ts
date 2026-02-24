/**
 * Projects API
 */
import client from './client';
import type { Project, ProjectDetail, DeleteConfirmation, ProjectMember} from '@/lib/types';

export const projectsAPI = {
  async list(skip = 0, limit = 100, datasetId?: number): Promise<ProjectDetail[]> {
    const response = await client.get<ProjectDetail[]>('/projects', {
      params: { skip, limit, dataset_id: datasetId },
    });
    return response.data;
  },

  // Convenience method alias
  async listProjects(skip = 0, limit = 100, datasetId?: number): Promise<ProjectDetail[]> {
    return this.list(skip, limit, datasetId);
  },

  async get(id: number): Promise<ProjectDetail> {
    const response = await client.get<ProjectDetail>(`/projects/${id}`);
    return response.data;
  },

  async create(name: string, datasetId: number | null, taskType = 'detect'): Promise<Project> {
    const response = await client.post<Project>('/projects', {
      name,
      dataset_id: datasetId,
      task_type: taskType,
    });
    return response.data;
  },

  async delete(id: number, confirmed = false): Promise<void | DeleteConfirmation> {
    try {
      await client.delete(`/projects/${id}`, {
        params: { confirmed }
      });
    } catch (error: any) {
      // If 400 with confirmation required, return the confirmation data
      if (error.response?.status === 400 && error.response?.data?.requires_confirmation) {
        return error.response.data as DeleteConfirmation;
      }
      throw error;
    }
  },

  // Team Management
  async getMembers(projectId: number): Promise<ProjectMember[]> {
    const response = await client.get<ProjectMember[]>(`/projects/${projectId}/members`);
    return response.data;
  },

  async addMember(projectId: number, userId: number): Promise<ProjectMember> {
    const response = await client.post<ProjectMember>(
      `/projects/${projectId}/members`,
      { user_id: userId }
    );
    return response.data;
  },

  async removeMember(projectId: number, userId: number): Promise<void> {
    await client.delete(`/projects/${projectId}/members/${userId}`);
  },
};
