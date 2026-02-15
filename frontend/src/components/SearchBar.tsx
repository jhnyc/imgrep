import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { Camera, Search, SendHorizontal, X } from 'lucide-react';
import { useRef, useState } from 'react';
import type { SearchResult } from '../api/client';
import { api } from '../api/client';

interface SearchBarProps {
    onSearch: (results: SearchResult[]) => void;
    onClearSearch: () => void;
    hasActiveSearch: boolean;
    strategy: string;
    projectionStrategy: string;
    overlapStrategy: string;
}

export default function SearchBar({
    onSearch,
    onClearSearch,
    hasActiveSearch,
    strategy,
    projectionStrategy,
    overlapStrategy
}: SearchBarProps) {
    const [searchQuery, setSearchQuery] = useState('');
    const [isSearching, setIsSearching] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleTextSearch = async () => {
        if (!searchQuery.trim() || isSearching) return;

        setIsSearching(true);
        try {
            const results = await api.searchText(
                searchQuery,
                1,
                strategy,
                projectionStrategy,
                overlapStrategy
            );
            onSearch(results.results);
        } catch (error) {
            console.error('Search failed:', error);
        } finally {
            setIsSearching(false);
        }
    };

    const handleImageSearch = async (file: File) => {
        if (!file) return;

        setIsSearching(true);
        try {
            const results = await api.searchImage(
                file,
                1,
                strategy,
                projectionStrategy,
                overlapStrategy
            );
            onSearch(results.results);
        } catch (error) {
            console.error('Image search failed:', error);
        } finally {
            setIsSearching(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleTextSearch();
        }
    };

    const handleClear = () => {
        setSearchQuery('');
        onClearSearch();
    };

    return (
        <TooltipProvider>
            <div className="fixed bottom-12 left-1/2 -translate-x-1/2 z-50 w-full max-w-xl px-4">
                <div
                    className="flex items-center gap-1 p-1.5 border-border border rounded-full bg-white/95 backdrop-blur-sm shadow-xl"
                >
                    {/* Search Icon / Clear Button */}
                    <div className="flex items-center pl-1">
                        {hasActiveSearch ? (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={handleClear}
                                        className="w-10 h-10 rounded-full text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all"
                                    >
                                        <X size={20} strokeWidth={1.5} />
                                    </Button>
                                </TooltipTrigger>
                                <TooltipContent side="top">
                                    <p className="text-xs">Clear search</p>
                                </TooltipContent>
                            </Tooltip>
                        ) : (
                            <div className="w-10 h-10 flex items-center justify-center text-gray-400">
                                <Search size={20} strokeWidth={1.5} />
                            </div>
                        )}
                    </div>

                    {/* Input Field */}
                    <Input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Search images by text..."
                        className="flex-1 bg-transparent border-none shadow-none focus-visible:ring-0 text-gray-800 placeholder-gray-400 text-sm h-10 px-2"
                        disabled={isSearching}
                    />

                    {/* Image Search Button */}
                    <div className="flex items-center gap-1 pr-1">
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => fileInputRef.current?.click()}
                                    disabled={isSearching}
                                    className="w-10 h-10 rounded-full text-gray-400 hover:text-blue-500 hover:bg-blue-50 transition-all"
                                >
                                    <Camera size={20} strokeWidth={1.5} />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="top">
                                <p className="text-xs">Search by image</p>
                            </TooltipContent>
                        </Tooltip>

                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/*"
                            className="hidden"
                            onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) handleImageSearch(file);
                            }}
                        />

                        {/* Send/Search Button */}
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    onClick={handleTextSearch}
                                    disabled={!searchQuery.trim() || isSearching}
                                    className={cn(
                                        "w-10 h-10 rounded-full transition-all shadow-md",
                                        searchQuery.trim() && !isSearching
                                            ? "bg-blue-500 text-white hover:bg-blue-600 hover:scale-105 active:scale-95"
                                            : "bg-gray-100 text-gray-300"
                                    )}
                                    size="icon"
                                >
                                    {isSearching ? (
                                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    ) : (
                                        <SendHorizontal size={18} strokeWidth={1.5} />
                                    )}
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="top">
                                <p className="text-xs">Search</p>
                            </TooltipContent>
                        </Tooltip>
                    </div>
                </div>

                {/* Hint text */}
                {hasActiveSearch && (
                    <p className="text-center text-[10px] font-medium text-gray-400 mt-2 tracking-wide uppercase">
                        Showing search results • Click <span className="text-gray-600 font-bold">×</span> to clear
                    </p>
                )}
            </div>
        </TooltipProvider>
    );
}
