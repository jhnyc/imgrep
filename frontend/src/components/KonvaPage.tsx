
import { useQuery } from '@tanstack/react-query';
import { useCallback, useRef, useState } from 'react';
import type { SearchResult } from '../api/client';
import { api, queryKeys } from '../api/client';
import ExcalidrawToolbar from './ExcalidrawToolbar';
import ImageViewer from './ImageViewer';
import InfiniteCanvas from './InfiniteCanvas';
import SearchBar from './SearchBar';

export default function KonvaPage() {
    const [, setSelectedDirectory] = useState<string | null>(null);
    const [searchResults, setSearchResults] = useState<number[] | null>(null);
    const [isLocked, setIsLocked] = useState(false);
    const recenterRef = useRef<(() => void) | null>(null);
    const focusOnImageRef = useRef<((imageId: number) => void) | null>(null);
    const [strategy, setStrategy] = useState('hdbscan');
    const [projection, setProjection] = useState('umap');
    const [overlap, setOverlap] = useState('none');
    const [jitterAmount, setJitterAmount] = useState(10);
    const [explosionEnabled, setExplosionEnabled] = useState(false);

    const {
        data: clustersData,
        isLoading: isLoadingClusters,
        refetch: refetchClusters,
    } = useQuery({
        queryKey: queryKeys.clusters(strategy, projection, overlap, false),
        queryFn: () => api.getClusters(strategy, projection, overlap, false),
        enabled: true,
    });

    const handleAddDirectory = async (path: string) => {
        try {
            const result = await api.addDirectory(path);
            setSelectedDirectory(path);

            const pollJob = async () => {
                const status = await api.getJobStatus(result.job_id);
                if (status.status === 'completed') {
                    refetchClusters();
                } else if (status.status === 'error') {
                    console.error('Job failed:', status.errors);
                } else {
                    setTimeout(pollJob, 1000);
                }
            };
            setTimeout(pollJob, 1000);
        } catch (error) {
            console.error('Failed to add directory:', error);
        }
    };

    const handleSearch = (results: SearchResult[]) => {
        const resultIds = results.map(r => r.image_id);
        setSearchResults(resultIds);
        if (results.length > 0) {
            handleFocusImage(results[0].image_id);
        }
    };

    const clearSearch = () => {
        setSearchResults(null);
    };

    const handleToggleLock = useCallback(() => {
        setIsLocked((prev) => !prev);
    }, []);

    const handleRecenter = useCallback(() => {
        if (recenterRef.current) {
            recenterRef.current();
        }
    }, []);

    const registerRecenter = useCallback((fn: () => void) => {
        recenterRef.current = fn;
    }, []);

    const handleFocusImage = useCallback((imageId: number) => {
        if (focusOnImageRef.current) {
            focusOnImageRef.current(imageId);
        }
    }, []);

    const registerFocusOnImage = useCallback((fn: (imageId: number) => void) => {
        focusOnImageRef.current = fn;
    }, []);

    return (
        <div className="w-full h-screen excalidraw-bg overflow-hidden relative">
            <ExcalidrawToolbar
                onAddDirectory={handleAddDirectory}
                onRefresh={() => refetchClusters()}
                isLoadingClusters={isLoadingClusters}
                totalImages={clustersData?.total_images}
                clusterCount={clustersData?.clusters.length}
                isLocked={isLocked}
                onToggleLock={handleToggleLock}
                onRecenter={handleRecenter}
                onFocusImage={handleFocusImage}
                currentStrategy={strategy}
                onStrategyChange={setStrategy}
                currentProjection={projection}
                onProjectionChange={setProjection}
                currentOverlap={overlap}
                onOverlapChange={setOverlap}
                jitterAmount={jitterAmount}
                onJitterAmountChange={setJitterAmount}
                explosionEnabled={explosionEnabled}
                onExplosionEnabledChange={setExplosionEnabled}
            />

            {clustersData && (
                <InfiniteCanvas
                    clusters={clustersData.clusters}
                    images={clustersData.images}
                    searchResults={searchResults}
                    isLocked={isLocked}
                    onToggleLock={handleToggleLock}
                    onRecenter={handleRecenter}
                    registerRecenter={registerRecenter}
                    registerFocusOnImage={registerFocusOnImage}
                    explosionEnabled={explosionEnabled}
                />
            )}

            <SearchBar
                onSearch={handleSearch}
                onClearSearch={clearSearch}
                hasActiveSearch={searchResults !== null}
                strategy={strategy}
                projectionStrategy={projection}
                overlapStrategy={overlap}
            />

            <ImageViewer />
        </div>
    );
}
