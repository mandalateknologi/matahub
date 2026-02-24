/**
 * Recognition Catalogs API
 */
import client from './client';
import type {
  RecognitionCatalog,
  RecognitionCatalogDetail,
  RecognitionCatalogCreate,
  RecognitionCatalogUpdate,
  RecognitionLabel,
  RecognitionLabelDetail,
  RecognitionLabelCreate,
  RecognitionLabelUpdate,
  RecognitionImage,
  RecognitionJob,
  SimilaritySearchRequest,
  SimilaritySearchResponse,
  RecognitionCatalogStats
} from '../types/recognition';

export const recognitionCatalogsAPI = {
  // ===== Catalog Operations =====
  
  async listCatalogs(skip = 0, limit = 100, category?: string): Promise<RecognitionCatalog[]> {
    const params: any = { skip, limit };
    if (category) {
      params.category = category;
    }
    const response = await client.get<RecognitionCatalog[]>('/recognition-catalogs', { params });
    return response.data;
  },

  async listCategories(): Promise<string[]> {
    const response = await client.get<string[]>('/recognition-catalogs/categories');
    return response.data;
  },

  async getCatalog(catalogId: number): Promise<RecognitionCatalogDetail> {
    const response = await client.get<RecognitionCatalogDetail>(`/recognition-catalogs/${catalogId}`);
    return response.data;
  },

  async createCatalog(data: RecognitionCatalogCreate): Promise<RecognitionCatalog> {
    const response = await client.post<RecognitionCatalog>('/recognition-catalogs', data);
    return response.data;
  },

  async updateCatalog(catalogId: number, data: RecognitionCatalogUpdate): Promise<RecognitionCatalog> {
    const response = await client.patch<RecognitionCatalog>(`/recognition-catalogs/${catalogId}`, data);
    return response.data;
  },

  async deleteCatalog(catalogId: number): Promise<void> {
    await client.delete(`/recognition-catalogs/${catalogId}`);
  },

  async getCatalogStats(catalogId: number): Promise<RecognitionCatalogStats> {
    const response = await client.get<RecognitionCatalogStats>(`/recognition-catalogs/${catalogId}/stats`);
    return response.data;
  },

  // ===== Label Operations =====

  async listLabels(catalogId: number): Promise<RecognitionLabel[]> {
    const response = await client.get<RecognitionLabel[]>(`/recognition-catalogs/${catalogId}/labels`);
    return response.data;
  },

  async getLabel(catalogId: number, labelId: number): Promise<RecognitionLabelDetail> {
    const response = await client.get<RecognitionLabelDetail>(`/recognition-catalogs/${catalogId}/labels/${labelId}`);
    return response.data;
  },

  async createLabel(catalogId: number, data: RecognitionLabelCreate): Promise<RecognitionLabel> {
    const response = await client.post<RecognitionLabel>(`/recognition-catalogs/${catalogId}/labels`, data);
    return response.data;
  },

  async updateLabel(catalogId: number, labelId: number, data: RecognitionLabelUpdate): Promise<RecognitionLabel> {
    const response = await client.patch<RecognitionLabel>(`/recognition-catalogs/${catalogId}/labels/${labelId}`, data);
    return response.data;
  },

  async deleteLabel(catalogId: number, labelId: number): Promise<void> {
    await client.delete(`/recognition-catalogs/${catalogId}/labels/${labelId}`);
  },

  // ===== Image Operations =====

  async uploadImages(catalogId: number, labelId: number, files: File[]): Promise<RecognitionImage[]> {
    const formData = new FormData();
    
    files.forEach((file) => {
      formData.append('files', file);
    });

    const response = await client.post<RecognitionImage[]>(
      `/recognition-catalogs/${catalogId}/labels/${labelId}/images`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  getImageUrl(catalogId: number, labelId: number, imageId: number, thumbnail = false): string {
    const params = thumbnail ? '?thumbnail=true' : '';
    return `/api/recognition-catalogs/${catalogId}/labels/${labelId}/images/${imageId}${params}`;
  },

  // ===== Similarity Search =====

  async searchSimilar(
    catalogId: number,
    queryImage: File,
    searchParams?: SimilaritySearchRequest
  ): Promise<SimilaritySearchResponse> {
    const formData = new FormData();
    formData.append('query_image', queryImage);
    
    if (searchParams) {
      formData.append('search_params', JSON.stringify(searchParams));
    }

    const response = await client.post<SimilaritySearchResponse>(
      `/recognition-catalogs/${catalogId}/search`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  // ===== Semantic Text Search =====

  async searchByText(
    catalogId: number,
    textQuery: string,
    searchParams?: { top_k?: number; threshold?: number; label_filter?: number[] }
  ): Promise<SimilaritySearchResponse> {
    const formData = new FormData();
    formData.append('text_query', textQuery);
    
    if (searchParams) {
      if (searchParams.top_k !== undefined) {
        formData.append('top_k', searchParams.top_k.toString());
      }
      if (searchParams.threshold !== undefined) {
        formData.append('threshold', searchParams.threshold.toString());
      }
      if (searchParams.label_filter) {
        formData.append('label_filter', JSON.stringify(searchParams.label_filter));
      }
    }

    const response = await client.post<SimilaritySearchResponse>(
      `/recognition-catalogs/${catalogId}/search/text`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  // ===== Job Status =====

  async getJobStatus(jobId: number): Promise<RecognitionJob> {
    const response = await client.get<RecognitionJob>(`/recognition-catalogs/jobs/${jobId}`);
    return response.data;
  },

  // ===== ZIP Upload =====

  async uploadZip(catalogId: number, zipFile: File): Promise<{ message: string; labels_created: number; images_uploaded: number; catalog_id: number }> {
    const formData = new FormData();
    formData.append('file', zipFile);

    const response = await client.post(
      `/recognition-catalogs/${catalogId}/upload-zip`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },
};

export default recognitionCatalogsAPI;
