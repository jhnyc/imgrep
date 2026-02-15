import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuSeparator,
    DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { Play, Settings, Zap } from "lucide-react";
import React from "react";
import { ToolbarButton } from "./ToolbarButton";

interface SettingsDropdownProps {
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
}

export function SettingsDropdown({
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
}: SettingsDropdownProps) {
    const [open, setOpen] = React.useState(false);

    return (
        <DropdownMenu open={open} onOpenChange={setOpen}>
            <Tooltip>
                <TooltipTrigger asChild>
                    <DropdownMenuTrigger asChild>
                        <ToolbarButton
                            active={open}
                            icon={<Settings size={18} strokeWidth={1.5} />}
                            className="mr-2"
                        />
                    </DropdownMenuTrigger>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-xs">
                    <p>Settings</p>
                </TooltipContent>
            </Tooltip>
            <DropdownMenuContent align="start" className="w-64 p-3 bg-white/95 backdrop-blur-md rounded-xl border-gray-100 shadow-xl">
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
                                        className={cn(
                                            "flex-1 flex items-center gap-2 px-2 py-1.5 rounded-lg transition-all text-left",
                                            currentStrategy === s.id
                                                ? 'bg-blue-50 text-blue-600'
                                                : 'hover:bg-gray-50 text-gray-600'
                                        )}
                                    >
                                        <div className={cn(
                                            "w-2 h-2 rounded-full",
                                            isBuilt(s.id, currentProjection, currentOverlap) ? 'bg-green-500' : 'bg-gray-300'
                                        )} />
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

                    <DropdownMenuSeparator className="bg-gray-100" />

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
                                        className={cn(
                                            "flex-1 flex items-center gap-2 px-2 py-1.5 rounded-lg transition-all text-left",
                                            currentProjection === p.id
                                                ? 'bg-blue-50 text-blue-600'
                                                : 'hover:bg-gray-50 text-gray-600'
                                        )}
                                    >
                                        <div className={cn(
                                            "w-2 h-2 rounded-full",
                                            isBuilt(currentStrategy, p.id, currentOverlap) ? 'bg-green-500' : 'bg-gray-300'
                                        )} />
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

                    <DropdownMenuSeparator className="bg-gray-100" />

                    {/* Overlap Reduction Section */}
                    <div>
                        <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2 px-1">Overlap Reduction</h4>
                        <div className="space-y-2">
                            <div className="flex bg-gray-100/50 p-0.5 rounded-lg border border-gray-100">
                                {['none', 'jitter'].map((o) => (
                                    <button
                                        key={o}
                                        onClick={() => onOverlapChange(o)}
                                        className={cn(
                                            "flex-1 px-2 py-1 text-[10px] font-bold rounded-md transition-all",
                                            currentOverlap === o
                                                ? 'bg-white text-blue-600 shadow-sm'
                                                : 'text-gray-400 hover:text-gray-600'
                                        )}
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
                                    <Slider
                                        defaultValue={[jitterAmount]}
                                        min={5}
                                        max={50}
                                        step={5}
                                        onValueChange={(vals) => onJitterAmountChange(vals[0])}
                                        className="py-2"
                                    />
                                </div>
                            )}
                        </div>
                    </div>

                    <DropdownMenuSeparator className="bg-gray-100" />

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
                        <Switch
                            checked={explosionEnabled}
                            onCheckedChange={onExplosionEnabledChange}
                        />
                    </div>
                </div>
            </DropdownMenuContent>
        </DropdownMenu>
    );
}
