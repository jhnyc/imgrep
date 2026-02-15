import type { ImageListItem } from "@/api/client";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { ArrowDownAZ, Check, ChevronDown, Clock, RefreshCw, Search } from "lucide-react";
import React, { useCallback, useEffect, useState } from "react";

interface StatsDropdownProps {
    totalImages?: number;
    clusterCount?: number;
    onFocusImage: (imageId: number) => void;
}

type SortOption = 'name' | 'newest' | 'oldest';

export function StatsDropdown({
    totalImages,
    clusterCount,
    onFocusImage,
}: StatsDropdownProps) {
    const [open, setOpen] = useState(false);
    const [filenameSearch, setFilenameSearch] = useState('');
    const [sortBy, setSortBy] = useState<SortOption>('name');
    const [images, setImages] = useState<ImageListItem[]>([]);
    const [isLoadingImages, setIsLoadingImages] = useState(false);

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

    const handleImageClick = (imageId: number) => {
        onFocusImage(imageId);
        setOpen(false);
    };

    return (
        <DropdownMenu open={open} onOpenChange={setOpen}>
            <DropdownMenuTrigger asChild>
                <button
                    className="flex items-center gap-1.5 text-xs text-gray-500 bg-white/90 backdrop-blur-sm px-3 py-2 rounded-lg hover:bg-gray-50 transition-all shadow-sm border border-gray-100"
                >
                    <span className="font-semibold text-gray-700">{totalImages?.toLocaleString()}</span>
                    <span>images</span>
                    <span className="text-gray-300">•</span>
                    <span className="font-semibold text-gray-700">{clusterCount}</span>
                    <span>clusters</span>
                    <ChevronDown size={14} strokeWidth={2} className={cn("ml-1 transition-transform", open && "rotate-180")} />
                </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-72 p-0 bg-white rounded-xl overflow-hidden shadow-xl border-gray-100">
                {/* Search */}
                <div className="p-3 border-b border-gray-100">
                    <div className="relative">
                        <Search size={16} className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400" />
                        <Input
                            value={filenameSearch}
                            onChange={(e) => setFilenameSearch(e.target.value)}
                            placeholder="Search..."
                            className="pl-8 h-8 text-xs bg-gray-50/50 border-gray-200 focus-visible:ring-blue-500/20 focus-visible:border-blue-400"
                            autoFocus
                        />
                    </div>
                </div>

                {/* Sort options */}
                <div className="flex items-center gap-1 p-2 py-1 border-b border-gray-100 bg-gray-50/50">
                    <span className="text-[10px] text-gray-400 px-2 font-bold uppercase tracking-wider">Sort:</span>
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
                <ScrollArea className="h-64 h-min-32">
                    {isLoadingImages ? (
                        <div className="flex items-center justify-center py-8">
                            <RefreshCw size={20} className="animate-spin text-gray-400" />
                        </div>
                    ) : images.length === 0 ? (
                        <div className="text-center py-8 text-sm text-gray-400">
                            No images found
                        </div>
                    ) : (
                        <div className="py-1">
                            {images.map((img) => (
                                <button
                                    key={img.id}
                                    onClick={() => handleImageClick(img.id)}
                                    className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 transition-colors text-left"
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
                            ))}
                        </div>
                    )}
                </ScrollArea>
            </DropdownMenuContent>
        </DropdownMenu>
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
        <Button
            variant="ghost"
            size="sm"
            onClick={onClick}
            className={cn(
                "h-7 px-2 gap-1.5 text-[10px] font-medium",
                active ? 'bg-blue-100 text-blue-600 hover:bg-blue-100 hover:text-blue-600' : 'text-gray-500 hover:bg-gray-100'
            )}
        >
            {icon}
            <span>{label}</span>
            {active && <Check size={12} strokeWidth={2} />}
        </Button>
    );
}
