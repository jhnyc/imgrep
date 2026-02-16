import type { JobStatus, TrackedDirectory } from "@/api/client";
import { api, queryKeys } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent
} from "@/components/ui/dialog";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { FolderPlus, Globe, HardDrive, Layers, Loader2, MoreVertical, Settings, Sliders } from "lucide-react";
import { useEffect, useState } from "react";
import { ToolbarButton } from "./ToolbarButton";

interface SettingsDialogProps {
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
    isBuilt: (strategy: string, projection: string, overlap?: string) => boolean;
    handleBuild: (s: string, p: string, o?: string) => Promise<void>;
    onAddDirectory: (path: string) => Promise<void>;
}

type Tab = 'general' | 'configuration' | 'clustering';

const IMAGE_EXTENSIONS_LIST = ["jpg", "jpeg", "png", "webp", "gif", "bmp", "tiff"];

export function SettingsDialog({
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
    isBuilt,
    handleBuild,
    onAddDirectory,
}: SettingsDialogProps) {
    const [open, setOpen] = useState(false);
    const [activeTab, setActiveTab] = useState<Tab>('general');
    const [newDirPath, setNewDirPath] = useState("");
    const [isAddingDir, setIsAddingDir] = useState(false);

    // Config states
    const [embeddingModel, setEmbeddingModel] = useState("jina-clip-v2");
    const [batchSize, setBatchSize] = useState(12);
    const [selectedExtensions, setSelectedExtensions] = useState<string[]>(["jpg", "jpeg", "png", "webp"]);
    const [autoReindex, setAutoReindex] = useState(true);
    const [syncFrequency, setSyncFrequency] = useState("1h");

    // Fetch tracked directories
    const { data: directoriesData, refetch: refetchDirs } = useQuery({
        queryKey: queryKeys.trackedDirectories(),
        queryFn: () => api.listTrackedDirectories(),
        enabled: open,
    });

    // Fetch global settings
    const { data: settingsData, refetch: refetchSettings } = useQuery({
        queryKey: ['settings'],
        queryFn: async () => {
            const res = await fetch('http://localhost:8001/api/settings');
            if (!res.ok) throw new Error("Failed to fetch settings");
            return res.json();
        },
        enabled: open,
    });

    // Sync local state with fetched settings
    useEffect(() => {
        if (settingsData) {
            setEmbeddingModel(settingsData.embedding_model);
            setBatchSize(settingsData.batch_size);
            setSelectedExtensions(settingsData.image_extensions);
            setAutoReindex(settingsData.auto_reindex);
            setSyncFrequency(settingsData.sync_frequency);
        }
    }, [settingsData]);

    const updateSettings = async (updates: any) => {
        try {
            await fetch('http://localhost:8001/api/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    embedding_model: embeddingModel,
                    batch_size: batchSize,
                    image_extensions: selectedExtensions,
                    auto_reindex: autoReindex,
                    sync_frequency: syncFrequency,
                    ...updates
                })
            });
            refetchSettings();
        } catch (e) {
            console.error(e);
        }
    };

    // Update handlers wrapper
    const handleEmbeddingChange = (v: string) => { setEmbeddingModel(v); updateSettings({ embedding_model: v }); };
    const handleBatchSizeChange = (v: number) => { setBatchSize(v); updateSettings({ batch_size: v }); };
    const handleExtensionsChange = (v: string[]) => { setSelectedExtensions(v); updateSettings({ image_extensions: v }); };
    const handleAutoReindexChange = (v: boolean) => { setAutoReindex(v); updateSettings({ auto_reindex: v }); };
    const handleSyncFrequencyChange = (v: string) => { setSyncFrequency(v); updateSettings({ sync_frequency: v }); };

    // Fetch active jobs
    const { data: jobsData } = useQuery({
        queryKey: queryKeys.jobs(),
        queryFn: () => api.listJobs(),
        enabled: open,
        refetchInterval: open ? 2000 : undefined,
    });

    useEffect(() => {
        if (open && jobsData) {
            console.log("[DEBUG] Active Jobs Data:", jobsData.jobs);
        }
    }, [open, jobsData]);

    const handleAddDir = async () => {
        if (!newDirPath.trim()) return;
        setIsAddingDir(true);
        try {
            let seconds = 3600;
            if (syncFrequency.endsWith('m')) seconds = parseInt(syncFrequency) * 60;
            else if (syncFrequency.endsWith('h')) seconds = parseInt(syncFrequency) * 3600;
            else if (syncFrequency.endsWith('d')) seconds = parseInt(syncFrequency) * 86400;

            await api.addTrackedDirectory(newDirPath.trim(), 'snapshot', seconds);
            setNewDirPath("");
            refetchDirs();
        } catch (error) {
            console.error(error);
        } finally {
            setIsAddingDir(false);
        }
    };

    const handleRemoveDirectory = async (id: number) => {
        try {
            await api.removeTrackedDirectory(id);
            refetchDirs();
        } catch (error) {
            console.error(error);
        }
    };

    const handleReindexDirectory = async (id: number) => {
        try {
            await api.syncTrackedDirectory(id);
            // We force a refetch to verify status
            refetchDirs();
        } catch (error) {
            console.error(error);
        }
    };

    const sidebarItems = [
        { id: 'general', label: 'General', icon: Globe },
        { id: 'configuration', label: 'Settings', icon: Sliders },
        { id: 'clustering', label: 'Clustering', icon: Layers },
    ];

    const trackedDirectories = directoriesData?.directories || [];
    const activeJobs = jobsData?.jobs.filter(j => j.status === 'processing' || j.status === 'pending') || [];

    // Calculate overall progress from database counts
    const totalProcessed = trackedDirectories.reduce((acc, dir) => acc + dir.processed_count, 0);
    const totalImages = trackedDirectories.reduce((acc, dir) => acc + dir.total_count, 0);

    // We only show overall progress if there's an actual active sync happening
    const isSyncingWorkspace = activeJobs.length > 0;
    const overallProgress = totalImages > 0 ? (totalProcessed / totalImages) * 100 : 0;



    return (
        <>
            <Tooltip>
                <TooltipTrigger asChild>
                    <ToolbarButton
                        active={open}
                        onClick={() => setOpen(true)}
                        icon={<Settings size={18} strokeWidth={1.5} />}
                        className="mr-2"
                    />
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-xs">
                    <p>Settings</p>
                </TooltipContent>
            </Tooltip>

            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent className="max-w-[1000px] p-0 h-[700px] overflow-hidden rounded-lg border-gray-200 shadow-2xl bg-white gap-0">
                    <div className="flex h-full w-full">
                        {/* Sidebar */}
                        <div className="w-[260px] bg-[#fbfbfa] border-r border-gray-200/60 p-4 space-y-1 shrink-0">
                            {sidebarItems.map((item) => (
                                <button
                                    key={item.id}
                                    onClick={() => setActiveTab(item.id as Tab)}
                                    className={cn(
                                        "w-full flex items-center gap-2.5 px-3 py-1.5 rounded text-[14px] transition-colors text-left",
                                        activeTab === item.id
                                            ? "bg-[#efefee] text-gray-900 font-medium"
                                            : "text-gray-600 hover:bg-[#efefee]/60"
                                    )}
                                >
                                    <item.icon size={16} className="shrink-0" />
                                    {item.label}
                                </button>
                            ))}
                        </div>

                        {/* Content */}
                        <div className="flex-1 flex flex-col h-full overflow-hidden bg-white">
                            <div className="px-10 py-8 shrink-0">
                                <h1 className="text-[20px] font-bold text-gray-900">
                                    {sidebarItems.find(i => i.id === activeTab)?.label}
                                </h1>
                            </div>

                            <ScrollArea className="flex-1 px-10 pb-10">
                                <div className="max-w-[700px] space-y-10">
                                    {activeTab === 'general' && (
                                        <div className="space-y-10">
                                            {/* Tracked Directories */}
                                            <div className="space-y-6">
                                                <div className="space-y-1">
                                                    <h2 className="text-[16px] font-semibold text-gray-900">Connected Sources</h2>
                                                    <p className="text-[13px] text-gray-500">Manage the folders indexed in your workspace.</p>
                                                </div>

                                                {totalImages > 0 && (
                                                    <div className={cn(
                                                        "p-4 rounded-lg border space-y-3 transition-colors",
                                                        isSyncingWorkspace
                                                            ? "bg-blue-50/50 border-blue-100"
                                                            : "bg-gray-50/50 border-gray-100"
                                                    )}>
                                                        <div className="flex justify-between items-end">
                                                            <div className="space-y-0.5">
                                                                <div className={cn(
                                                                    "text-[12px]",
                                                                    isSyncingWorkspace ? "text-blue-700/70" : "text-gray-500"
                                                                )}>
                                                                    {totalProcessed.toLocaleString()} of {totalImages.toLocaleString()} images indexed
                                                                </div>
                                                            </div>
                                                            <div className={cn(
                                                                "text-[14px] font-bold",
                                                                isSyncingWorkspace ? "text-blue-900" : "text-gray-900"
                                                            )}>
                                                                {Math.round(overallProgress)}%
                                                            </div>
                                                        </div>
                                                        <Progress
                                                            value={overallProgress}
                                                            className={cn(
                                                                "h-2",
                                                                isSyncingWorkspace ? "bg-blue-100" : "bg-gray-200"
                                                            )}
                                                        />
                                                    </div>
                                                )}
                                                <div className="divide-y divide-gray-100 border-t border-gray-100">
                                                    {trackedDirectories.map((dir) => {
                                                        const dirJob = activeJobs.find(j => {
                                                            if (!j.directory_path) return false;
                                                            return j.directory_path.replace(/\/$/, '') === dir.path.replace(/\/$/, '');
                                                        });

                                                        return (
                                                            <DirectoryItem
                                                                key={dir.id}
                                                                directory={dir}
                                                                job={dirJob}
                                                                onRemove={handleRemoveDirectory}
                                                                onReindex={handleReindexDirectory}
                                                            />
                                                        );
                                                    })}
                                                    {trackedDirectories.length === 0 && (
                                                        <div className="py-10 text-center text-gray-400 text-[13px]">
                                                            No folders connected yet.
                                                        </div>
                                                    )}
                                                </div>
                                                <div className="flex gap-2">
                                                    <Input
                                                        placeholder="Add local directory path..."
                                                        className="h-9 text-[14px] bg-white border-gray-300 focus-visible:ring-0 focus-visible:border-gray-400 placeholder:text-gray-400 transition-all rounded shadow-sm"
                                                        value={newDirPath}
                                                        onChange={(e) => setNewDirPath(e.target.value)}
                                                    />
                                                    <Button
                                                        variant="outline"
                                                        className="h-9 px-4 gap-2 bg-white hover:bg-gray-50 text-[13px] font-medium border-gray-300 rounded shadow-sm shrink-0"
                                                        onClick={handleAddDir}
                                                        disabled={isAddingDir || !newDirPath.trim()}
                                                    >
                                                        {isAddingDir ? <Loader2 size={14} className="animate-spin" /> : <FolderPlus size={14} />}
                                                        Add folder
                                                    </Button>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {activeTab === 'configuration' && (
                                        <div className="space-y-10">
                                            {/* Inference Engine */}
                                            <div className="flex items-start justify-between">
                                                <div className="space-y-1 max-w-[440px]">
                                                    <h2 className="text-[14px] font-medium text-gray-900">Inference Engine</h2>
                                                    <p className="text-[13px] text-gray-500 leading-relaxed">Select the computer vision model used for semantic search and feature extraction.</p>
                                                </div>
                                                <Select value={embeddingModel} onValueChange={handleEmbeddingChange}>
                                                    <SelectTrigger className="w-[180px] h-8 text-[13px] bg-white border-gray-300 rounded focus:ring-0 shadow-sm">
                                                        <SelectValue placeholder="Select model" />
                                                    </SelectTrigger>
                                                    <SelectContent className="bg-white border-gray-200 shadow-xl z-[100] min-w-[200px] rounded-lg">
                                                        <SelectItem value="jina-clip-v2" className="py-2 text-[13px] focus:bg-gray-100">Jina CLIP v3</SelectItem>
                                                        <SelectItem value="vit-base" className="py-2 text-[13px] focus:bg-gray-100">ViT-Base-L14</SelectItem>
                                                        <SelectItem value="siglip" className="py-2 text-[13px] focus:bg-gray-100">SigLIP-v2</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                            </div>

                                            {/* Batch Size */}
                                            <div className="space-y-4 pt-8 border-t border-gray-100">
                                                <div className="flex items-start justify-between">
                                                    <div className="space-y-1 max-w-[440px]">
                                                        <h2 className="text-[14px] font-medium text-gray-900">Processing Throughput</h2>
                                                        <p className="text-[13px] text-gray-500 leading-relaxed">Adjust the number of images processed in parallel during indexing.</p>
                                                    </div>
                                                    <div className="text-[13px] font-medium text-gray-900">{batchSize} images/batch</div>
                                                </div>
                                                <div className="px-2">
                                                    <Slider
                                                        value={[batchSize]}
                                                        onValueChange={(v) => handleBatchSizeChange(v[0])}
                                                        max={64}
                                                        min={1}
                                                        step={1}
                                                        className="w-full"
                                                    />
                                                </div>
                                            </div>

                                            {/* Extensions */}
                                            <div className="space-y-4 pt-8 border-t border-gray-100">
                                                <div className="space-y-1">
                                                    <h2 className="text-[14px] font-medium text-gray-900">Indexing extensions</h2>
                                                    <p className="text-[13px] text-gray-500 leading-relaxed">Choose which file formats will be indexed during directory scans.</p>
                                                </div>
                                                <ToggleGroup
                                                    type="multiple"
                                                    value={selectedExtensions}
                                                    onValueChange={handleExtensionsChange}
                                                    className="justify-start flex-wrap gap-2"
                                                >
                                                    {IMAGE_EXTENSIONS_LIST.map((ext) => (
                                                        <ToggleGroupItem
                                                            key={ext}
                                                            value={ext}
                                                            className="px-2.5 py-1 h-7 text-[12px] font-medium uppercase border border-gray-200 rounded hover:bg-gray-50 data-[state=on]:bg-gray-900 data-[state=on]:text-white data-[state=on]:border-gray-900 transition-colors"
                                                        >
                                                            {ext}
                                                        </ToggleGroupItem>
                                                    ))}
                                                </ToggleGroup>
                                            </div>

                                            {/* Automatic Re-indexing */}
                                            <div className="space-y-6 pt-8 border-t border-gray-100">
                                                <div className="flex items-center justify-between">
                                                    <div className="space-y-1">
                                                        <h2 className="text-[14px] font-medium text-gray-900">Automatic re-indexing</h2>
                                                        <p className="text-[13px] text-gray-500">Enable background synchronization for connected folders.</p>
                                                    </div>
                                                    <Switch
                                                        checked={autoReindex}
                                                        onCheckedChange={handleAutoReindexChange}
                                                        className="data-[state=checked]:bg-[#2577D8]"
                                                    />
                                                </div>

                                                {autoReindex && (
                                                    <div className="flex items-center justify-between">
                                                        <div className="space-y-1">
                                                            <h2 className="text-[14px] font-medium text-gray-900">Sync frequency</h2>
                                                            <p className="text-[13px] text-gray-500">How often the backend checks for file changes.</p>
                                                        </div>
                                                        <Select value={syncFrequency} onValueChange={handleSyncFrequencyChange}>
                                                            <SelectTrigger className="w-[140px] h-8 text-[13px] bg-white border-gray-300 rounded focus:ring-0 shadow-sm">
                                                                <SelectValue />
                                                            </SelectTrigger>
                                                            <SelectContent className="bg-white border-gray-200 shadow-xl z-[100] min-w-[160px] rounded-lg">
                                                                <SelectItem value="15m" className="py-2 text-[13px] focus:bg-gray-100">Every 15 mins</SelectItem>
                                                                <SelectItem value="1h" className="py-2 text-[13px] focus:bg-gray-100">Every hour</SelectItem>
                                                                <SelectItem value="6h" className="py-2 text-[13px] focus:bg-gray-100">Every 6 hours</SelectItem>
                                                                <SelectItem value="24h" className="py-2 text-[13px] focus:bg-gray-100">Daily</SelectItem>
                                                            </SelectContent>
                                                        </Select>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}

                                    {activeTab === 'clustering' && (
                                        <div className="space-y-10">
                                            {/* Strategy Engine Section */}
                                            <div className="space-y-6">
                                                <div className="space-y-1">
                                                    <h2 className="text-[16px] font-semibold text-gray-900">Strategy Engine</h2>
                                                    <p className="text-[13px] text-gray-500">Determine how images are grouped based on visual similarity.</p>
                                                </div>

                                                <div className="divide-y divide-gray-100">
                                                    {[
                                                        { id: 'hdbscan', label: 'HDBSCAN', desc: 'Density-based with automatic cluster discovery.' },
                                                        { id: 'kmeans', label: 'K-Means', desc: 'Centroid-based strategy for uniform distribution.' },
                                                        { id: 'dbscan', label: 'DBSCAN', desc: 'Fixed neighbor analysis with density constraints.' },
                                                    ].map((s) => (
                                                        <div key={s.id} className="py-4 flex items-center justify-between gap-4">
                                                            <div className="space-y-0.5">
                                                                <div className="flex items-center gap-2">
                                                                    <div className={cn(
                                                                        "w-2 h-2 rounded-full",
                                                                        isBuilt(s.id, currentProjection, currentOverlap)
                                                                            ? "bg-emerald-500"
                                                                            : "bg-gray-200"
                                                                    )} />
                                                                    <span className="text-[14px] font-medium text-gray-900">{s.label}</span>
                                                                </div>
                                                                <p className="text-[13px] text-gray-500">{s.desc}</p>
                                                            </div>
                                                            <div className="flex items-center gap-2">
                                                                {!isBuilt(s.id, currentProjection, currentOverlap) && (
                                                                    <Button
                                                                        size="sm"
                                                                        variant="outline"
                                                                        className="h-8 px-3 text-[12px] font-medium text-gray-600 rounded border-gray-300 transition-all hover:bg-gray-50"
                                                                        onClick={() => handleBuild(s.id, currentProjection, currentOverlap)}
                                                                    >
                                                                        Recompute
                                                                    </Button>
                                                                )}
                                                                <Switch
                                                                    checked={currentStrategy === s.id}
                                                                    onCheckedChange={(checked) => checked && onStrategyChange(s.id)}
                                                                    className="data-[state=checked]:bg-[#2577D8]"
                                                                />
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>

                                            {/* Layout Projection Section */}
                                            <div className="space-y-6 pt-8 border-t border-gray-100">
                                                <div className="flex items-center justify-between">
                                                    <div className="space-y-1">
                                                        <h2 className="text-[14px] font-medium text-gray-900">Layout projection</h2>
                                                        <p className="text-[13px] text-gray-500">Algorithm used to flatten embeddings into 2D.</p>
                                                    </div>
                                                    <Select value={currentProjection} onValueChange={(v) => onProjectionChange(v)}>
                                                        <SelectTrigger className="w-[120px] h-8 text-[13px] bg-white border-gray-300 rounded focus:ring-0 shadow-sm">
                                                            <SelectValue />
                                                        </SelectTrigger>
                                                        <SelectContent className="bg-white border-gray-200 shadow-xl z-[100] min-w-[180px] rounded-lg">
                                                            <SelectItem value="umap" className="py-2 text-[13px] focus:bg-gray-100">UMAP</SelectItem>
                                                            <SelectItem value="pca" className="py-2 text-[13px] focus:bg-gray-100">PCA</SelectItem>
                                                            <SelectItem value="tsne" className="py-2 text-[13px] focus:bg-gray-100">t-SNE</SelectItem>
                                                        </SelectContent>
                                                    </Select>
                                                </div>
                                            </div>

                                            {/* Geometric Spacing Section */}
                                            <div className="space-y-6 pt-8 border-t border-gray-100">
                                                <div className="flex items-center justify-between">
                                                    <div className="space-y-1">
                                                        <h2 className="text-[14px] font-medium text-gray-900">Overlap reduction</h2>
                                                        <p className="text-[13px] text-gray-500">Displacement strategy for dense clusters.</p>
                                                    </div>
                                                    <ToggleGroup
                                                        type="single"
                                                        value={currentOverlap}
                                                        onValueChange={(v) => v && onOverlapChange(v)}
                                                        className="bg-[#f0f0ef] p-0.5 rounded"
                                                    >
                                                        <ToggleGroupItem value="none" className="text-[12px] font-medium rounded px-3 h-7 data-[state=on]:bg-white data-[state=on]:shadow-sm text-gray-600 data-[state=on]:text-gray-900 border-0">None</ToggleGroupItem>
                                                        <ToggleGroupItem value="jitter" className="text-[12px] font-medium rounded px-3 h-7 data-[state=on]:bg-white data-[state=on]:shadow-sm text-gray-600 data-[state=on]:text-gray-900 border-0">Jitter</ToggleGroupItem>
                                                    </ToggleGroup>
                                                </div>

                                                {currentOverlap === 'jitter' && (
                                                    <div className="flex items-center justify-between gap-10">
                                                        <div className="space-y-1 shrink-0">
                                                            <h2 className="text-[13px] font-medium text-gray-700">Jitter intensity</h2>
                                                            <p className="text-[12px] text-gray-400">Current: {jitterAmount}px</p>
                                                        </div>
                                                        <div className="flex-1 max-w-[300px] px-2">
                                                            <Slider
                                                                value={[jitterAmount]}
                                                                min={5}
                                                                max={50}
                                                                step={5}
                                                                onValueChange={(vals) => onJitterAmountChange(vals[0])}
                                                                className="w-full"
                                                            />
                                                        </div>
                                                    </div>
                                                )}
                                            </div>

                                            {/* Reactive Explosion Section */}
                                            <div className="flex items-center justify-between pt-8 border-t border-gray-100">
                                                <div className="space-y-1">
                                                    <h2 className="text-[14px] font-medium text-gray-900">Reactive explosion</h2>
                                                    <p className="text-[13px] text-gray-500">Expand layouts dynamically when hovering over dense areas.</p>
                                                </div>
                                                <Switch
                                                    checked={explosionEnabled}
                                                    onCheckedChange={onExplosionEnabledChange}
                                                    className="data-[state=checked]:bg-blue-600"
                                                />
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </ScrollArea>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </>
    );
}

function DirectoryItem({ directory, job, onRemove, onReindex }: { directory: TrackedDirectory, job?: JobStatus, onRemove: (id: number) => void, onReindex: (id: number) => void }) {
    // isProcessing is true if there's an active background job
    const isSyncing = job && (job.status === 'processing' || job.status === 'pending');

    // We get actual progress from the database counts provided by the backend
    const processed = directory.processed_count;
    const total = directory.total_count;
    const progress = total > 0 ? (processed / total) * 100 : 0;

    return (
        <div className="py-4 flex flex-col gap-3 group transition-colors">
            <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                    <div className={cn(
                        "p-1.5 rounded bg-gray-50 text-gray-400 shrink-0",
                        isSyncing && "text-blue-500 bg-blue-50 animate-pulse"
                    )}>
                        <HardDrive size={16} />
                    </div>
                    <div className="min-w-0">
                        <div className="text-[14px] font-medium text-gray-900 truncate tracking-tight">{directory.path}</div>
                        <div className="text-[12px] text-gray-500 mt-0.5 flex items-center gap-2">
                            <span className="capitalize">{directory.sync_strategy} sync</span>
                            <span>•</span>
                            <span>{total.toLocaleString()} files</span>
                            {directory.last_synced_at && !isSyncing && (
                                <>
                                    <span>•</span>
                                    <span>Last synced: {new Date(directory.last_synced_at).toLocaleString()}</span>
                                </>
                            )}
                            {isSyncing && (
                                <>
                                    <span>•</span>
                                    <span className="text-blue-600 font-medium animate-pulse">Syncing...</span>
                                </>
                            )}
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                    {(isSyncing || (processed < total && total > 0)) && (
                        <div className="text-right">
                            <div className="text-[12px] font-bold text-blue-600">
                                {Math.round(progress)}%
                            </div>
                        </div>
                    )}

                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 w-7 p-0 text-gray-400 hover:text-gray-600 hover:bg-gray-100 data-[state=open]:bg-gray-100 opacity-0 group-hover:opacity-100 data-[state=open]:opacity-100 transition-all rounded-full"
                            >
                                <MoreVertical size={16} />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-[160px]">
                            <DropdownMenuItem
                                onClick={() => onReindex(directory.id)}
                                disabled={!!isSyncing}
                            >
                                Reindex now
                            </DropdownMenuItem>
                            <DropdownMenuItem
                                onClick={() => onRemove(directory.id)}
                                className="text-red-600 focus:text-red-600 focus:bg-red-50"
                            >
                                Disconnect
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>
            {(isSyncing || (processed < total && total > 0)) && (
                <div className="space-y-1.5">
                    <Progress value={progress} className="h-1 bg-blue-100" />
                </div>
            )}
        </div>
    );
}
