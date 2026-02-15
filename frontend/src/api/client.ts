const API_BASE = 'http://localhost:8001';

// Types
export interface JobStatus {
  job_id: string;
  status: string;
  progress: number;
  total: number;
  processed: number;
  errors: string[];
  directory_path?: string;
}

export interface TrackedDirectory {
  id: number;
  path: string;
  sync_strategy: string;
  is_active: boolean;
  last_synced_at: string | null;
  last_error: string | null;
  sync_interval_seconds: number;
  created_at: string;
  file_count?: number;
}

export interface ClusterNode {
  id: number;
  x: number;
  y: number;
  image_count: number;
}

export interface ImagePosition {
  id: number;
  x: number;
  y: number;
  cluster_label: number | null;
  thumbnail_url: string;
}

export interface ClustersResponse {
  clustering_run_id: number;
  strategy: string;
  projection_strategy: string;
  clusters: ClusterNode[];
  images: ImagePosition[];
  total_images: number;
}

export interface ClusteringStatus {
  built_combinations: {
    strategy: string;
    projection_strategy: string;
    overlap_strategy: string;
  }[];
}

export interface SearchResult {
  image_id: number;
  similarity: number;
  thumbnail_url: string;
  x?: number;
  y?: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
}

export interface ImageDetails {
  id: number;
  file_path: string;
  file_name: string;
  width: number | null;
  height: number | null;
  thumbnail_url: string;
  cluster_label: number | null;
}

export interface ImageListItem {
  id: number;
  file_name: string;
  thumbnail_url: string;
}

export interface ImageListResponse {
  images: ImageListItem[];
  total: number;
}

// API functions
export const api = {
  // Directories
  addDirectory: async (path: string) => {
    const response = await fetch(`${API_BASE}/api/directories/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to add directory');
    }
    return response.json();
  },

  uploadFiles: async (files: FileList) => {
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    // Uses /upload endpoint
    const response = await fetch(`${API_BASE}/api/directories/upload`, {
        method: 'POST',
        body: formData,
    });
    
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to upload files');
    }
    return response.json();
  },

  getJobStatus: async (jobId: string): Promise<JobStatus> => {
    const response = await fetch(`${API_BASE}/api/directories/job/${jobId}`);
    if (!response.ok) throw new Error('Failed to get job status');
    return response.json();
  },

  listTrackedDirectories: async (): Promise<{ directories: TrackedDirectory[] }> => {
    const response = await fetch(`${API_BASE}/api/directories/tracked`);
    if (!response.ok) throw new Error('Failed to list tracked directories');
    return response.json();
  },

  addTrackedDirectory: async (path: string, syncStrategy = 'snapshot', syncInterval = 300): Promise<TrackedDirectory> => {
    const response = await fetch(`${API_BASE}/api/directories/tracked`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            path,
            sync_strategy: syncStrategy,
            sync_interval_seconds: syncInterval
        }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to add tracked directory');
    }
    return response.json();
  },

  listJobs: async (): Promise<{ jobs: JobStatus[] }> => {
    const response = await fetch(`${API_BASE}/api/directories/jobs`);
    if (!response.ok) throw new Error('Failed to list jobs');
    return response.json();
  },
  
  removeTrackedDirectory: async (directoryId: number) => {
    const response = await fetch(`${API_BASE}/api/directories/tracked/${directoryId}`, {
        method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to remove directory');
    return response.json();
  },

  // Clusters
  getClusters: async (strategy = 'hdbscan', projection_strategy = 'umap', overlap_strategy = 'none', forceRecompute = false): Promise<ClustersResponse> => {
    const params = new URLSearchParams({
      strategy,
      projection_strategy,
      overlap_strategy,
      ...(forceRecompute && { force_recompute: 'true' }),
    });
    const response = await fetch(`${API_BASE}/api/clusters?${params}`);
    if (!response.ok) throw new Error('Failed to get clusters');
    return response.json();
  },

  getClusteringStatus: async (): Promise<ClusteringStatus> => {
    const response = await fetch(`${API_BASE}/api/clusters/status`);
    if (!response.ok) throw new Error('Failed to get clustering status');
    return response.json();
  },

  recomputeClusters: async (strategy = 'hdbscan', projection_strategy = 'umap', overlap_strategy = 'none', parameters?: Record<string, unknown>): Promise<ClustersResponse> => {
    const response = await fetch(`${API_BASE}/api/clusters/recompute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        strategy,
        projection_strategy,
        overlap_strategy,
        parameters,
      }),
    });
    if (!response.ok) throw new Error('Failed to recompute clusters');
    return response.json();
  },

  // Images
  getImageDetails: async (imageId: number): Promise<ImageDetails> => {
    const response = await fetch(`${API_BASE}/api/images/${imageId}`);
    if (!response.ok) throw new Error('Failed to get image details');
    return response.json();
  },

  getThumbnailUrl: (path: string) => `${API_BASE}/api/thumbnails/${path}`,
  getOriginalImageUrl: (imageId: number) => `${API_BASE}/api/images/${imageId}/view`,

  listImages: async (
    search?: string,
    sortBy: 'name' | 'newest' | 'oldest' = 'name',
    limit = 100,
    offset = 0
  ): Promise<ImageListResponse> => {
    const params = new URLSearchParams({
      sort_by: sortBy,
      limit: String(limit),
      offset: String(offset),
    });
    if (search) params.set('search', search);
    
    const response = await fetch(`${API_BASE}/api/images/list?${params}`);
    if (!response.ok) throw new Error('Failed to list images');
    return response.json();
  },

  // Search
  searchText: async (
    query: string, 
    topK = 20, 
    strategy = 'hdbscan', 
    projection_strategy = 'umap', 
    overlap_strategy = 'none'
  ): Promise<SearchResponse> => {
    const response = await fetch(`${API_BASE}/api/search/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        query, 
        top_k: topK,
        strategy,
        projection_strategy,
        overlap_strategy
      }),
    });
    if (!response.ok) throw new Error('Failed to search by text');
    return response.json();
  },

  searchImage: async (
    file: File, 
    topK = 20,
    strategy = 'hdbscan', 
    projection_strategy = 'umap', 
    overlap_strategy = 'none'
  ): Promise<SearchResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const params = new URLSearchParams({
      top_k: String(topK),
      strategy,
      projection_strategy,
      overlap_strategy
    });

    const response = await fetch(`${API_BASE}/api/search/image?${params}`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) throw new Error('Failed to search by image');
    return response.json();
  },
};

// Query keys for React Query
export const queryKeys = {
  jobStatus: (jobId: string) => ['job', jobId] as const,
  clusters: (strategy: string, projectionStrategy: string, overlapStrategy: string, forceRecompute: boolean) =>
    ['clusters', strategy, projectionStrategy, overlapStrategy, forceRecompute] as const,
  imageDetails: (imageId: number) => ['image', imageId] as const,
  searchResults: (query: string) => ['search', query] as const,
  clusteringStatus: () => ['clusters', 'status'] as const,
  trackedDirectories: () => ['directories', 'tracked'] as const,
  jobs: () => ['directories', 'jobs'] as const,
};
