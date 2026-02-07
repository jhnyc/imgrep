import {
    ArrowDownAZ,
    Check,
    ChevronDown,
    Clock,
    Crosshair,
    FolderPlus,
    Lock,
    MousePointer2,
    RefreshCw,
    Search,
    Unlock,
    X
} from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import type { ImageListItem } from '../api/client';
import { api } from '../api/client';

interface ExcalidrawToolbarProps {
    onAddDirectory: (path: string) => Promise<void>;
    onRefresh: () => void;
    isLoadingClusters: boolean;
    totalImages?: number;
    clusterCount?: number;
    isLocked: boolean;
    onToggleLock: () => void;
    onRecenter: () => void;
    onFocusImage: (imageId: number) => void;
}

type SortOption = 'name' | 'newest' | 'oldest';

export default function ExcalidrawToolbar({
    onAddDirectory,
    onRefresh,
    isLoadingClusters,
    totalImages,
    clusterCount,
    isLocked,
    onToggleLock,
    onRecenter,
    onFocusImage,
}: ExcalidrawToolbarProps) {
    const [showAddDirModal, setShowAddDirModal] = useState(false);
    const [showStatsDropdown, setShowStatsDropdown] = useState(false);

    const [directoryPath, setDirectoryPath] = useState('');
    const [isAddingDir, setIsAddingDir] = useState(false);
    const [addDirError, setAddDirError] = useState<string | null>(null);

    // Stats dropdown state
    const [filenameSearch, setFilenameSearch] = useState('');
    const [sortBy, setSortBy] = useState<SortOption>('name');
    const [images, setImages] = useState<ImageListItem[]>([]);
    const [isLoadingImages, setIsLoadingImages] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

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
    useEffect(() => {
        if (!showStatsDropdown) return;

        const fetchImages = async () => {
            setIsLoadingImages(true);
            try {
                const result = await api.listImages(
                    filenameSearch || undefined,
                    sortBy,
                    50
                );
                setImages(result.images);
            } catch (err) {
                console.error('Failed to fetch images:', err);
            } finally {
                setIsLoadingImages(false);
            }
        };

        const debounce = setTimeout(fetchImages, 300);
        return () => clearTimeout(debounce);
    }, [showStatsDropdown, filenameSearch, sortBy]);

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
                        <h3 className="font-semibold text-gray-800 text-base mb-4">Add Directory</h3>

                        <form onSubmit={handleAddDirSubmit} className="space-y-4">
                            <div>
                                <label className="text-xs font-medium text-gray-500 block mb-2">Absolute Path</label>
                                <input
                                    type="text"
                                    value={directoryPath}
                                    onChange={(e) => {
                                        setDirectoryPath(e.target.value);
                                        setAddDirError(null);
                                    }}
                                    className={`w-full px-3 py-2.5 rounded-xl border bg-gray-50/50 focus:outline-none focus:ring-2 transition-all font-mono text-sm ${addDirError
                                        ? 'border-red-300 focus:ring-red-100 focus:border-red-400'
                                        : 'border-gray-200 focus:ring-blue-500/20 focus:border-blue-400'
                                        }`}
                                    placeholder="/Users/name/Photos"
                                    autoFocus
                                />
                                {addDirError && (
                                    <p className="text-red-500 text-xs mt-2 font-medium flex items-center gap-1">
                                        <X size={12} strokeWidth={2} />
                                        {addDirError}
                                    </p>
                                )}
                            </div>

                            <button
                                type="submit"
                                disabled={isAddingDir || !directoryPath.trim()}
                                className="w-full py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-xl transition-all flex items-center justify-center gap-2 text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {isAddingDir ? (
                                    <RefreshCw size={16} strokeWidth={2} className="animate-spin" />
                                ) : (
                                    <FolderPlus size={16} strokeWidth={2} />
                                )}
                                <span>Start Processing</span>
                            </button>
                        </form>
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
