import { Camera, Search, SendHorizontal, X } from 'lucide-react';
import { useRef, useState } from 'react';
import { api } from '../api/client';

interface SearchBarProps {
    onSearch: (resultIds: number[]) => void;
    onClearSearch: () => void;
    hasActiveSearch: boolean;
}

export default function SearchBar({ onSearch, onClearSearch, hasActiveSearch }: SearchBarProps) {
    const [searchQuery, setSearchQuery] = useState('');
    const [isSearching, setIsSearching] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleTextSearch = async () => {
        if (!searchQuery.trim() || isSearching) return;

        setIsSearching(true);
        try {
            const results = await api.searchText(searchQuery, 50);
            const resultIds = results.results.map((r) => r.image_id);
            onSearch(resultIds);
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
            const results = await api.searchImage(file, 50);
            const resultIds = results.results.map((r) => r.image_id);
            onSearch(resultIds);
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
        <div className="fixed bottom-12 left-1/2 -translate-x-1/2 z-50 w-full max-w-xl px-4">
            <div
                className="relative flex items-center gap-2 p-2 rounded-full bg-white/95 backdrop-blur-sm"
                style={{ boxShadow: '0 0 0 1px rgba(0,0,0,0.08), 0 4px 24px rgba(0,0,0,0.12)' }}
            >
                {/* Search Icon / Clear Button */}
                {hasActiveSearch ? (
                    <button
                        onClick={handleClear}
                        className="w-9 h-9 flex items-center justify-center rounded-xl text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-all"
                        title="Clear search"
                    >
                        <X size={20} strokeWidth={1.5} />
                    </button>
                ) : (
                    <div className="w-9 h-9 flex items-center justify-center text-gray-400">
                        <Search size={20} strokeWidth={1.5} />
                    </div>
                )}

                {/* Input Field */}
                <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Search images by text..."
                    className="flex-1 bg-transparent border-none outline-none text-gray-800 placeholder-gray-400 text-sm py-2"
                    disabled={isSearching}
                />

                {/* Image Search Button */}
                <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isSearching}
                    className="w-9 h-9 flex items-center justify-center rounded-xl text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-all disabled:opacity-50"
                    title="Search by image"
                >
                    <Camera size={20} strokeWidth={1.5} />
                </button>
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
                <button
                    onClick={handleTextSearch}
                    disabled={!searchQuery.trim() || isSearching}
                    className={`w-9 h-9 flex items-center justify-center rounded-full transition-all ${searchQuery.trim() && !isSearching
                        ? 'bg-blue-500 text-white hover:bg-blue-600'
                        : 'bg-gray-100 text-gray-300'
                        }`}
                    title="Search"
                >
                    {isSearching ? (
                        <div className="w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
                    ) : (
                        <SendHorizontal size={18} strokeWidth={1.5} />
                    )}
                </button>
            </div>

            {/* Hint text */}
            {hasActiveSearch && (
                <p className="text-center text-xs text-gray-400 mt-2 animate-fade-in">
                    Showing search results • Click <span className="font-medium">×</span> to clear
                </p>
            )}
        </div>
    );
}
