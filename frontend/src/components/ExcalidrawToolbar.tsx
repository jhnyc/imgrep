import { useQuery } from '@tanstack/react-query';
import {
    ArrowDownAZ,
    Check,
    ChevronDown,
    Clock,
    Crosshair,
    FolderOpen,
    FolderPlus,
    Lock,
    MousePointer2,
    Play,
    RefreshCw,
    Search,
    Settings,
    Unlock,
    Upload,
    X,
    Zap
} from 'lucide-react';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import type { ImageListItem } from '../api/client';
import { api, queryKeys } from '../api/client';

interface ExcalidrawToolbarProps {
    onAddDirectory: (path: string) => Promise<void>;
    onUploadFiles: (files: FileList) => Promise<void>;
    onRefresh: () => void;
    isLoadingClusters: boolean;
    totalImages?: number;
    clusterCount?: number;
    isLocked: boolean;
    onToggleLock: () => void;
    onRecenter: () => void;
    onFocusImage: (imageId: number) => void;
    currentStrategy: string;
    onStrategyChange: (strategy: string) => void;
    currentProjection: string;
    onProjectionChange: (projection: string) => void;
    currentOverlap: string;
    onOverlapChange: (overlap: string) => void;
    jitterAmount: number;
    onJitterAmountChange: (amount: number) => void;
    explosionEnabled: boolean;
    onExplosionEnabledChange: (enabled: boolean) => void;
}

type SortOption = 'name' | 'newest' | 'oldest';

export default function ExcalidrawToolbar({
    onAddDirectory,
    onUploadFiles,
    onRefresh,
    isLoadingClusters,
    totalImages,
    clusterCount,
    isLocked,
    onToggleLock,
    onRecenter,
    onFocusImage,
    currentStrategy,
    onStrategyChange,
    currentProjection,
    onProjectionChange,
    currentOverlap,
    onOverlapChange,
    jitterAmount,
    onJitterAmountChange,
    explosionEnabled,
    onExplosionEnabledChange,
}: ExcalidrawToolbarProps) {
    const [showAddDirModal, setShowAddDirModal] = useState(false);
    const [showStatsDropdown, setShowStatsDropdown] = useState(false);
    const [showSettingsDropdown, setShowSettingsDropdown] = useState(false);

    const [directoryPath, setDirectoryPath] = useState('');
    const [isAddingDir, setIsAddingDir] = useState(false);
    const [addDirError, setAddDirError] = useState<string | null>(null);
    const [isDraggingFolder, setIsDraggingFolder] = useState(false);

    // Stats dropdown state
    const [filenameSearch, setFilenameSearch] = useState('');
    const [sortBy, setSortBy] = useState<SortOption>('name');
    const [images, setImages] = useState<ImageListItem[]>([]);
    const [isLoadingImages, setIsLoadingImages] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const settingsRef = useRef<HTMLDivElement>(null);

    // Fetch clustering status
    const { data: statusData, refetch: refetchStatus } = useQuery({
        queryKey: queryKeys.clusteringStatus(),
        queryFn: () => api.getClusteringStatus(),
        refetchInterval: 5000,
    });

    const isBuilt = (strategy: string, projection: string, overlap: string = 'none') => {
        return statusData?.built_combinations.some(
            c => c.strategy === strategy &&
                c.projection_strategy === projection &&
                c.overlap_strategy === overlap
        );
    };

    const handleBuild = async (s: string, p: string, o: string = 'none') => {
        try {
            await api.recomputeClusters(s, p, o, { jitter_amount: jitterAmount });
            refetchStatus();
        } catch (err) {
            console.error('Failed to build:', err);
        }
    };

    const closeModal = () => {
        setShowAddDirModal(false);
        setAddDirError(null);
    };

    const handleAddDirSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!directoryPath.trim()) return;

        setIsAddingDir(true);
        setAddDirError(null);
        try {
            await onAddDirectory(directoryPath.trim());
            setDirectoryPath('');
            closeModal();
        } catch (error: any) {
            console.error('Failed to add directory:', error);
            setAddDirError(error.message || 'Failed to add directory');
        } finally {
            setIsAddingDir(false);
        }
    };

    // Fetch images when dropdown opens or search/sort changes
    // Fetch images with polling
    const fetchImages = useCallback(async (showLoading = true) => {
        if (showLoading) setIsLoadingImages(true);
        try {
            const result = await api.listImages(
                filenameSearch || undefined,
                sortBy,
                50
            );
            setImages(prev => {
                if (JSON.stringify(prev) === JSON.stringify(result.images)) {
                    return prev;
                }
                return result.images;
            });
        } catch (err) {
            console.error('Failed to fetch images:', err);
        } finally {
            if (showLoading) setIsLoadingImages(false);
        }
    }, [filenameSearch, sortBy]);

    // Initial fetch and on search/sort change
    useEffect(() => {
        const debounce = setTimeout(() => fetchImages(true), 300);
        return () => clearTimeout(debounce);
    }, [fetchImages]);

    // Poll every 5 seconds
    useEffect(() => {
        const interval = setInterval(() => {
            fetchImages(false);
        }, 5000);
        return () => clearInterval(interval);
    }, [fetchImages]);

    // Close dropdown on click outside
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setShowStatsDropdown(false);
            }
        };

        if (showStatsDropdown) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [showStatsDropdown]);

    // Close settings dropdown on click outside
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
                setShowSettingsDropdown(false);
            }
        };

        if (showSettingsDropdown) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [showSettingsDropdown]);

    const handleImageClick = (imageId: number) => {
        onFocusImage(imageId);
        setShowStatsDropdown(false);
    };

    return (
        <>
            {/* Top Center - Main Toolbar */}
            <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
                <div
                    className="flex items-center gap-1 p-1.5 rounded-xl bg-white/95 backdrop-blur-sm"
                    style={{ boxShadow: '0 0 0 1px rgba(0,0,0,0.08), 0 2px 12px rgba(0,0,0,0.08)' }}
                >
                    <ToolButton
                        active={isLocked}
                        onClick={onToggleLock}
                        icon={isLocked ? <Lock size={18} strokeWidth={1.5} /> : <Unlock size={18} strokeWidth={1.5} />}
                        title={isLocked ? "Unlock Canvas" : "Lock Canvas"}
                    />

                    <div className="w-px h-6 bg-gray-200 mx-0.5" />

                    <ToolButton
                        active={false}
                        onClick={() => { }}
                        icon={<MousePointer2 size={18} strokeWidth={1.5} />}
                        title="Selection"
                        shortcut="1"
                    />

                    <ToolButton
                        active={showAddDirModal}
                        onClick={() => {
                            setShowAddDirModal(true);
                            setAddDirError(null);
                        }}
                        icon={<FolderPlus size={18} strokeWidth={1.5} />}
                        title="Add Directory"
                        shortcut="2"
                    />

                    <div className="w-px h-6 bg-gray-200 mx-0.5" />

                    <ToolButton
                        active={false}
                        onClick={onRecenter}
                        icon={<Crosshair size={18} strokeWidth={1.5} />}
                        title="Recenter View"
                        shortcut="3"
                    />

                    <ToolButton
                        active={isLoadingClusters}
                        onClick={onRefresh}
                        icon={<RefreshCw size={18} strokeWidth={1.5} className={isLoadingClusters ? "animate-spin" : ""} />}
                        title="Refresh"
                    />

                    <div className="w-px h-6 bg-gray-200 mx-0.5" />

                    <div className="relative flex items-center pr-2" ref={settingsRef}>
                        <ToolButton
                            active={showSettingsDropdown}
                            onClick={() => setShowSettingsDropdown(!showSettingsDropdown)}
                            icon={<Settings size={18} strokeWidth={1.5} />}
                            title="Clustering Settings"
                        />

                        {showSettingsDropdown && (
                            <div
                                className="absolute top-full left-0 mt-2 w-64 bg-white/95 backdrop-blur-md rounded-xl p-3 border border-gray-100 animate-fade-in"
                                style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.12)' }}
                            >
                                <div className="space-y-4">
                                    {/* Clustering Strategy Section */}
                                    <div>
                                        <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2 px-1">Clustering Strategy</h4>
                                        <div className="space-y-1">
                                            {[
                                                { id: 'hdbscan', label: 'HDBSCAN', desc: 'Density-based' },
                                                { id: 'kmeans', label: 'K-Means', desc: 'Centroid-based' },
                                                { id: 'dbscan', label: 'DBSCAN', desc: 'Fixed-epsilon' },
                                            ].map((s) => (
                                                <div key={s.id} className="flex items-center group">
                                                    <button
                                                        onClick={() => onStrategyChange(s.id)}
                                                        className={`flex-1 flex items-center gap-2 px-2 py-1.5 rounded-lg transition-all text-left ${currentStrategy === s.id
                                                            ? 'bg-blue-50 text-blue-600'
                                                            : 'hover:bg-gray-50 text-gray-600'
                                                            }`}
                                                    >
                                                        <div className={`w-2 h-2 rounded-full ${isBuilt(s.id, currentProjection, currentOverlap) ? 'bg-green-500' : 'bg-gray-300'}`} />
                                                        <div className="flex-1">
                                                            <div className="text-xs font-semibold leading-none">{s.label}</div>
                                                            <div className="text-[10px] text-gray-400 mt-1">{s.desc}</div>
                                                        </div>
                                                    </button>
                                                    {!isBuilt(s.id, currentProjection, currentOverlap) && (
                                                        <button
                                                            onClick={(e) => { e.stopPropagation(); handleBuild(s.id, currentProjection, currentOverlap); }}
                                                            className="p-2 text-gray-400 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity"
                                                            title="Build optimized version"
                                                        >
                                                            <Play size={14} fill="currentColor" />
                                                        </button>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="h-px bg-gray-100" />

                                    {/* Projection Strategy Section */}
                                    <div>
                                        <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2 px-1">2D Projection</h4>
                                        <div className="space-y-1">
                                            {[
                                                { id: 'umap', label: 'UMAP', desc: 'Fast non-linear' },
                                                { id: 'pca', label: 'PCA', desc: 'Preserves variance' },
                                                { id: 'tsne', label: 't-SNE', desc: 'Preserves local structure' },
                                            ].map((p) => (
                                                <div key={p.id} className="flex items-center group">
                                                    <button
                                                        onClick={() => onProjectionChange(p.id)}
                                                        className={`flex-1 flex items-center gap-2 px-2 py-1.5 rounded-lg transition-all text-left ${currentProjection === p.id
                                                            ? 'bg-blue-50 text-blue-600'
                                                            : 'hover:bg-gray-50 text-gray-600'
                                                            }`}
                                                    >
                                                        <div className={`w-2 h-2 rounded-full ${isBuilt(currentStrategy, p.id, currentOverlap) ? 'bg-green-500' : 'bg-gray-300'}`} />
                                                        <div className="flex-1">
                                                            <div className="text-xs font-semibold leading-none">{p.label}</div>
                                                            <div className="text-[10px] text-gray-400 mt-1">{p.desc}</div>
                                                        </div>
                                                    </button>
                                                    {!isBuilt(currentStrategy, p.id, currentOverlap) && (
                                                        <button
                                                            onClick={(e) => { e.stopPropagation(); handleBuild(currentStrategy, p.id, currentOverlap); }}
                                                            className="p-2 text-gray-400 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity"
                                                            title="Build optimized version"
                                                        >
                                                            <Play size={14} fill="currentColor" />
                                                        </button>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="h-px bg-gray-100" />

                                    {/* Overlap Reduction Section */}
                                    <div>
                                        <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2 px-1">Overlap Reduction</h4>
                                        <div className="space-y-2">
                                            <div className="flex bg-gray-100/50 p-0.5 rounded-lg border border-gray-100">
                                                {['none', 'jitter'].map((o) => (
                                                    <button
                                                        key={o}
                                                        onClick={() => onOverlapChange(o)}
                                                        className={`flex-1 px-2 py-1 text-[10px] font-bold rounded-md transition-all ${currentOverlap === o
                                                            ? 'bg-white text-blue-600 shadow-sm'
                                                            : 'text-gray-400 hover:text-gray-600'
                                                            }`}
                                                    >
                                                        {o.toUpperCase()}
                                                    </button>
                                                ))}
                                            </div>

                                            {currentOverlap === 'jitter' && (
                                                <div className="px-1 py-1">
                                                    <div className="flex justify-between text-[9px] font-bold text-gray-400 mb-1">
                                                        <span>JITTER AMOUNT</span>
                                                        <span className="text-blue-500">{jitterAmount}px</span>
                                                    </div>
                                                    <input
                                                        type="range"
                                                        min="5"
                                                        max="50"
                                                        step="5"
                                                        value={jitterAmount}
                                                        onChange={(e) => onJitterAmountChange(parseInt(e.target.value))}
                                                        className="w-full h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
                                                    />
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div className="h-px bg-gray-100" />

                                    {/* Interactive Explosion Toggle */}
                                    <div className="flex items-center justify-between px-1">
                                        <div className="flex items-center gap-2">
                                            <div className="p-1.5 bg-orange-50 text-orange-500 rounded-lg">
                                                <Zap size={14} fill="currentColor" />
                                            </div>
                                            <div>
                                                <div className="text-xs font-semibold leading-none">Explosion Effect</div>
                                                <div className="text-[10px] text-gray-400 mt-1">Fan out dense areas</div>
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => onExplosionEnabledChange(!explosionEnabled)}
                                            className={`w-8 h-4 rounded-full transition-colors relative ${explosionEnabled ? 'bg-blue-500' : 'bg-gray-200'
                                                }`}
                                        >
                                            <div className={`absolute top-0.5 left-0.5 w-3 h-3 bg-white rounded-full transition-transform ${explosionEnabled ? 'translate-x-4' : ''
                                                }`} />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Top Right - Stats Dropdown */}
            {(totalImages !== undefined || clusterCount !== undefined) && (
                <div className="fixed top-6 right-4 z-50" ref={dropdownRef}>
                    <button
                        onClick={() => setShowStatsDropdown(!showStatsDropdown)}
                        className="flex items-center gap-1.5 text-xs text-gray-500 bg-white/90 backdrop-blur-sm px-3 py-2 rounded-lg hover:bg-gray-50 transition-all"
                        style={{ boxShadow: '0 0 0 1px rgba(0,0,0,0.08), 0 2px 8px rgba(0,0,0,0.08)' }}
                    >
                        <span className="font-semibold text-gray-700">{totalImages?.toLocaleString()}</span>
                        <span>images</span>
                        <span className="text-gray-300">•</span>
                        <span className="font-semibold text-gray-700">{clusterCount}</span>
                        <span>clusters</span>
                        <ChevronDown size={14} strokeWidth={2} className={`ml-1 transition-transform ${showStatsDropdown ? 'rotate-180' : ''}`} />
                    </button>

                    {showStatsDropdown && (
                        <div
                            className="absolute top-full right-0 mt-2 w-72 bg-white rounded-xl overflow-hidden animate-fade-in"
                            style={{ boxShadow: '0 0 0 1px rgba(0,0,0,0.08), 0 8px 32px rgba(0,0,0,0.12)' }}
                        >
                            {/* Search */}
                            <div className="p-3 border-b border-gray-100">
                                <div className="relative">
                                    <Search size={16} className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400" />
                                    <input
                                        type="text"
                                        value={filenameSearch}
                                        onChange={(e) => setFilenameSearch(e.target.value)}
                                        placeholder="Search..."
                                        className="w-full pl-7 pr-3 py-1 rounded-lg border border-gray-200 bg-gray-50/50 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
                                        autoFocus
                                    />
                                </div>
                            </div>

                            {/* Sort options */}
                            <div className="flex items-center gap-1 p-2 py-1 border-b border-gray-100 bg-gray-50/50">
                                <span className="text-2xs text-gray-400 px-2">Sort:</span>
                                <SortButton
                                    active={sortBy === 'name'}
                                    onClick={() => setSortBy('name')}
                                    icon={<ArrowDownAZ size={14} />}
                                    label="Name"
                                />
                                <SortButton
                                    active={sortBy === 'newest'}
                                    onClick={() => setSortBy('newest')}
                                    icon={<Clock size={14} />}
                                    label="Newest"
                                />
                                <SortButton
                                    active={sortBy === 'oldest'}
                                    onClick={() => setSortBy('oldest')}
                                    icon={<Clock size={14} className="rotate-180" />}
                                    label="Oldest"
                                />
                            </div>

                            {/* Image list */}
                            <div className="max-h-64 min-h-32 overflow-y-auto">
                                {isLoadingImages ? (
                                    <div className="flex items-center justify-center py-8">
                                        <RefreshCw size={20} className="animate-spin text-gray-400" />
                                    </div>
                                ) : images.length === 0 ? (
                                    <div className="text-center py-8 text-sm text-gray-400">
                                        No images found
                                    </div>
                                ) : (
                                    images.map((img) => (
                                        <button
                                            key={img.id}
                                            onClick={() => handleImageClick(img.id)}
                                            className="w-full flex items-center gap-2 px-2.5 py-1.5 hover:bg-gray-50 transition-colors text-left"
                                        >
                                            <img
                                                src={`http://localhost:8001${img.thumbnail_url}`}
                                                alt=""
                                                className="w-7 h-7 rounded object-cover bg-gray-100 flex-shrink-0"
                                            />
                                            <span className="flex-1 text-xs text-gray-600 truncate">
                                                {img.file_name}
                                            </span>
                                        </button>
                                    ))
                                )}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Add Directory Modal */}
            {showAddDirModal && (
                <div className="fixed top-20 left-1/2 -translate-x-1/2 z-40">
                    <div
                        className="bg-white rounded-2xl p-5 w-80 md:w-96 relative animate-fade-in"
                        style={{ boxShadow: '0 0 0 1px rgba(0,0,0,0.08), 0 8px 32px rgba(0,0,0,0.12)' }}
                    >
                        <button
                            onClick={closeModal}
                            className="absolute top-3 right-3 w-7 h-7 flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-all"
                        >
                            <X size={16} strokeWidth={2} />
                        </button>
                        <h3 className="font-semibold text-gray-800 text-base mb-4">Add Images</h3>

                        {/* Drag & Drop Zone */}
                        <div
                            className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all ${isDraggingFolder
                                ? 'border-blue-400 bg-blue-50/50'
                                : 'border-gray-200 hover:border-gray-300'
                                }`}
                            onDragOver={(e) => {
                                e.preventDefault();
                                setIsDraggingFolder(true);
                            }}
                            onDragLeave={(e) => {
                                e.preventDefault();
                                setIsDraggingFolder(false);
                            }}
                            onDrop={async (e) => {
                                e.preventDefault();
                                setIsDraggingFolder(false);

                                const files: File[] = [];
                                const items = e.dataTransfer.items;

                                if (items) {
                                    // Handle dropped files/folders
                                    const entries: FileSystemEntry[] = [];
                                    for (let i = 0; i < items.length; i++) {
                                        const entry = items[i].webkitGetAsEntry?.();
                                        if (entry) entries.push(entry);
                                    }

                                    // Recursively read all files from dropped items
                                    const readEntries = async (entry: FileSystemEntry): Promise<void> => {
                                        if (entry.isFile) {
                                            const file = await new Promise<File>((resolve) => {
                                                (entry as FileSystemFileEntry).file(resolve);
                                            });
                                            if (file.type.startsWith('image/')) {
                                                files.push(file);
                                            }
                                        } else if (entry.isDirectory) {
                                            const reader = (entry as FileSystemDirectoryEntry).createReader();
                                            const entries = await new Promise<FileSystemEntry[]>((resolve) => {
                                                reader.readEntries(resolve);
                                            });
                                            for (const subEntry of entries) {
                                                await readEntries(subEntry);
                                            }
                                        }
                                    };

                                    for (const entry of entries) {
                                        await readEntries(entry);
                                    }
                                } else {
                                    // Fallback: use dataTransfer.files
                                    for (let i = 0; i < e.dataTransfer.files.length; i++) {
                                        const file = e.dataTransfer.files[i];
                                        if (file.type.startsWith('image/')) {
                                            files.push(file);
                                        }
                                    }
                                }

                                if (files.length > 0) {
                                    const fileList = new DataTransfer();
                                    files.forEach(f => fileList.items.add(f));
                                    setIsAddingDir(true);
                                    try {
                                        await onUploadFiles(fileList.files);
                                        closeModal();
                                    } catch (error: any) {
                                        setAddDirError(error.message || 'Failed to upload files');
                                    } finally {
                                        setIsAddingDir(false);
                                    }
                                }
                            }}
                        >
                            {isAddingDir ? (
                                <RefreshCw size={32} strokeWidth={1.5} className="mx-auto text-blue-500 mb-3 animate-spin" />
                            ) : (
                                <Upload size={32} strokeWidth={1.5} className="mx-auto text-gray-400 mb-3" />
                            )}
                            <p className="text-sm text-gray-600 font-medium">
                                {isAddingDir ? 'Uploading images...' : 'Drop images or folder here'}
                            </p>
                            <p className="text-xs text-gray-400 mt-1">or select files below</p>
                        </div>

                        {/* File Picker Buttons */}
                        <div className="mt-4 flex gap-2">
                            <label className="flex-1 py-2.5 bg-gray-100 hover:bg-gray-200 border border-gray-200 rounded-xl cursor-pointer transition-all flex items-center justify-center gap-2 text-sm font-medium text-gray-600">
                                <FolderOpen size={18} strokeWidth={2} />
                                <span>Select Folder</span>
                                <input
                                    type="file"
                                    webkitdirectory
                                    directory
                                    multiple
                                    className="hidden"
                                    onChange={async (e) => {
                                        const files = e.target.files;
                                        if (files && files.length > 0) {
                                            setIsAddingDir(true);
                                            setAddDirError(null);
                                            try {
                                                await onUploadFiles(files);
                                                closeModal();
                                            } catch (error: any) {
                                                setAddDirError(error.message || 'Failed to upload files');
                                            } finally {
                                                setIsAddingDir(false);
                                            }
                                        }
                                    }}
                                />
                            </label>
                            <label className="flex-1 py-2.5 bg-gray-100 hover:bg-gray-200 border border-gray-200 rounded-xl cursor-pointer transition-all flex items-center justify-center gap-2 text-sm font-medium text-gray-600">
                                <Upload size={18} strokeWidth={2} />
                                <span>Select Files</span>
                                <input
                                    type="file"
                                    accept="image/*"
                                    multiple
                                    className="hidden"
                                    onChange={async (e) => {
                                        const files = e.target.files;
                                        if (files && files.length > 0) {
                                            setIsAddingDir(true);
                                            setAddDirError(null);
                                            try {
                                                await onUploadFiles(files);
                                                closeModal();
                                            } catch (error: any) {
                                                setAddDirError(error.message || 'Failed to upload files');
                                            } finally {
                                                setIsAddingDir(false);
                                            }
                                        }
                                    }}
                                />
                            </label>
                        </div>

                        {/* Manual Path Entry */}
                        <div className="mt-4 pt-4 border-t border-gray-100">
                            <p className="text-xs text-gray-400 text-center mb-2">Or enter server path directly</p>
                            <form onSubmit={async (e) => {
                                e.preventDefault();
                                if (!directoryPath.trim()) return;
                                setIsAddingDir(true);
                                setAddDirError(null);
                                try {
                                    await onAddDirectory(directoryPath.trim());
                                    setDirectoryPath('');
                                    closeModal();
                                } catch (error: any) {
                                    setAddDirError(error.message || 'Failed to add directory');
                                } finally {
                                    setIsAddingDir(false);
                                }
                            }}>
                                <div className="flex gap-2">
                                    <input
                                        type="text"
                                        value={directoryPath}
                                        onChange={(e) => {
                                            setDirectoryPath(e.target.value);
                                            setAddDirError(null);
                                        }}
                                        className={`flex-1 px-3 py-2 rounded-xl border bg-gray-50/50 focus:outline-none focus:ring-2 transition-all font-mono text-sm ${addDirError
                                            ? 'border-red-300 focus:ring-red-100 focus:border-red-400'
                                            : 'border-gray-200 focus:ring-blue-500/20 focus:border-blue-400'
                                            }`}
                                        placeholder="/Users/name/Photos"
                                    />
                                    <button
                                        type="submit"
                                        disabled={isAddingDir || !directoryPath.trim()}
                                        className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-xl transition-all text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        Add
                                    </button>
                                </div>
                                {addDirError && (
                                    <p className="text-red-500 text-xs mt-2 font-medium flex items-center gap-1">
                                        <X size={12} strokeWidth={2} />
                                        {addDirError}
                                    </p>
                                )}
                            </form>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

function ToolButton({
    active,
    onClick,
    icon,
    title,
    shortcut,
}: {
    active: boolean;
    onClick: () => void;
    icon: React.ReactNode;
    title: string;
    shortcut?: string;
}) {
    return (
        <button
            onClick={onClick}
            title={title}
            className={`
                relative group w-9 h-9 flex items-center justify-center rounded-lg transition-all duration-150
                ${active
                    ? 'bg-blue-500 text-white'
                    : 'bg-transparent hover:bg-gray-100 text-gray-600'
                }
            `}
        >
            {icon}

            {shortcut && (
                <span className="absolute -bottom-0.5 left-1/2 -translate-x-1/2 text-[9px] font-medium text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    {shortcut}
                </span>
            )}
        </button>
    );
}

function SortButton({
    active,
    onClick,
    icon,
    label
}: {
    active: boolean;
    onClick: () => void;
    icon: React.ReactNode;
    label: string;
}) {
    return (
        <button
            onClick={onClick}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-2xs transition-all ${active
                ? 'bg-blue-100 text-blue-600'
                : 'text-gray-500 hover:bg-gray-100'
                }`}
        >
            {icon}
            <span>{label}</span>
            {active && <Check size={12} strokeWidth={2} />}
        </button>
    );
}

