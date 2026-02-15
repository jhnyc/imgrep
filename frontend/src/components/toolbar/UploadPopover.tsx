import { Button } from "@/components/ui/button";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { FolderOpen, FolderPlus, RefreshCw, Upload } from "lucide-react";
import React, { useState } from "react";
import { ToolbarButton } from "./ToolbarButton";

interface UploadPopoverProps {
    onUploadFiles: (files: FileList) => Promise<void>;
    onAddDirectory: (path: string) => Promise<void>;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function UploadPopover({
    onUploadFiles,
    onAddDirectory,
    open,
    onOpenChange,
}: UploadPopoverProps) {
    const [isAddingDir, setIsAddingDir] = useState(false);
    const [addDirError, setAddDirError] = useState<string | null>(null);
    const [isDraggingFolder, setIsDraggingFolder] = useState(false);
    const [directoryPath, setDirectoryPath] = useState('');

    const closePopover = () => {
        onOpenChange(false);
        setAddDirError(null);
        setDirectoryPath('');
    };

    const handleUpload = async (files: FileList | null) => {
        if (!files || files.length === 0) return;
        setIsAddingDir(true);
        setAddDirError(null);
        try {
            await onUploadFiles(files);
            closePopover();
        } catch (error) {
            const err = error as Error;
            setAddDirError(err.message || 'Failed to upload files');
        } finally {
            setIsAddingDir(false);
        }
    };

    const handleAddDirSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!directoryPath.trim()) return;

        setIsAddingDir(true);
        setAddDirError(null);
        try {
            await onAddDirectory(directoryPath.trim());
            closePopover();
        } catch (error) {
            const err = error as Error;
            setAddDirError(err.message || 'Failed to add directory');
        } finally {
            setIsAddingDir(false);
        }
    };

    return (
        <Popover open={open} onOpenChange={onOpenChange}>
            <Tooltip>
                <TooltipTrigger asChild>
                    <PopoverTrigger asChild>
                        <ToolbarButton
                            active={open}
                            icon={<FolderPlus size={18} strokeWidth={1.5} />}
                            shortcut="2"
                        />
                    </PopoverTrigger>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-xs">
                    <p>Add Images </p>
                </TooltipContent>
            </Tooltip>
            <PopoverContent align="center" side="bottom" className="w-80 mt-2 md:w-96 p-5 rounded-2xl border-gray-100 shadow-xl bg-white/95 backdrop-blur-md">
                {/* Error Message */}
                {addDirError && (
                    <div className="mb-4 p-2 bg-red-50 text-red-600 text-[10px] rounded-lg border border-red-100">
                        {addDirError}
                    </div>
                )}

                {/* Drag & Drop Zone */}
                <div
                    className={cn(
                        "relative border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer",
                        isDraggingFolder
                            ? 'border-blue-400 bg-blue-50/50'
                            : 'border-gray-200 hover:border-gray-300'
                    )}
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

                            for (let i = 0; i < items.length; i++) {
                                const entry = items[i].webkitGetAsEntry?.();
                                if (entry) await readEntries(entry);
                            }
                        } else {
                            for (let i = 0; i < e.dataTransfer.files.length; i++) {
                                const file = e.dataTransfer.files[i];
                                if (file.type.startsWith('image/')) files.push(file);
                            }
                        }

                        if (files.length > 0) {
                            const fileList = new DataTransfer();
                            files.forEach(f => fileList.items.add(f));
                            handleUpload(fileList.files);
                        }
                    }}
                >
                    {isAddingDir ? (
                        <RefreshCw size={32} strokeWidth={1.5} className="mx-auto text-blue-500 mb-3 animate-spin" />
                    ) : (
                        <Upload size={32} strokeWidth={1.5} className="mx-auto text-gray-400 mb-3" />
                    )}
                    <p className="text-xs text-gray-600 font-medium">
                        {isAddingDir ? 'Uploading images...' : 'Drop images or folder here'}
                    </p>
                </div>

                {/* File Picker Buttons */}
                <div className="mt-4 flex gap-2">
                    <label className="flex-1">
                        <Button variant="outline" className="w-full gap-2 border-gray-200 h-10 shadow-none text-xs" asChild>
                            <div className="cursor-pointer">
                                <FolderOpen size={16} strokeWidth={2} />
                                <span>Folder</span>
                                <input
                                    type="file"
                                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                                    {...({ webkitdirectory: "", directory: "" } as any)}
                                    multiple
                                    className="hidden"
                                    onChange={(e) => handleUpload(e.target.files)}
                                />
                            </div>
                        </Button>
                    </label>
                    <label className="flex-1">
                        <Button variant="outline" className="w-full gap-2 border-gray-200 h-10 shadow-none text-xs" asChild>
                            <div className="cursor-pointer">
                                <Upload size={16} strokeWidth={2} />
                                <span>Files</span>
                                <input
                                    type="file"
                                    accept="image/*"
                                    multiple
                                    className="hidden"
                                    onChange={(e) => handleUpload(e.target.files)}
                                />
                            </div>
                        </Button>
                    </label>
                </div>
            </PopoverContent>
        </Popover>
    );
}
