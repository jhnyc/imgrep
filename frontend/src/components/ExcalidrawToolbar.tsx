import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { useQuery } from '@tanstack/react-query';
import {
    Crosshair,
    Lock,
    MousePointer2,
    RefreshCw,
    Unlock
} from 'lucide-react';
import { useState } from 'react';
import { api, queryKeys } from '../api/client';
import { SettingsDropdown } from './toolbar/SettingsDropdown';
import { StatsDropdown } from './toolbar/StatsDropdown';
import { ToolbarButton } from './toolbar/ToolbarButton';
import { UploadPopover } from './toolbar/UploadPopover';

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

export default function ExcalidrawToolbar(props: ExcalidrawToolbarProps) {
    const [showUploadDialog, setShowUploadDialog] = useState(false);

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
        ) ?? false;
    };

    const handleBuild = async (s: string, p: string, o: string = 'none') => {
        try {
            await api.recomputeClusters(s, p, o, { jitter_amount: props.jitterAmount });
            refetchStatus();
        } catch (err) {
            console.error('Failed to build:', err);
        }
    };

    function ToolbarButtonWithTooltip({
        title,
        shortcut,
        ...rest
    }: React.ComponentProps<typeof ToolbarButton> & { title: string; shortcut?: string }) {
        return (
            <Tooltip>
                <TooltipTrigger asChild>
                    <ToolbarButton {...rest} shortcut={shortcut} />
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-xs">
                    <p>{title}</p>
                </TooltipContent>
            </Tooltip>
        );
    }

    return (
        <TooltipProvider>
            {/* Top Center - Main Toolbar */}
            <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
                <div
                    className="flex items-center gap-1 p-1.5 rounded-xl bg-white/95 backdrop-blur-sm shadow-xl border border-gray-100"
                >
                    <ToolbarButtonWithTooltip
                        active={props.isLocked}
                        onClick={props.onToggleLock}
                        icon={props.isLocked ? <Lock size={18} strokeWidth={1.5} /> : <Unlock size={18} strokeWidth={1.5} />}
                        title={props.isLocked ? "Unlock Canvas" : "Lock Canvas"}
                    />

                    <div className="w-px h-6 bg-gray-200 mx-0.5" />

                    <ToolbarButtonWithTooltip
                        active={false}
                        onClick={() => { }}
                        icon={<MousePointer2 size={18} strokeWidth={1.5} />}
                        title="Selection"
                        shortcut="1"
                    />

                    <UploadPopover
                        open={showUploadDialog}
                        onOpenChange={setShowUploadDialog}
                        onUploadFiles={props.onUploadFiles}
                        onAddDirectory={props.onAddDirectory}
                    />

                    <div className="w-px h-6 bg-gray-200 mx-0.5" />

                    <ToolbarButtonWithTooltip
                        active={false}
                        onClick={props.onRecenter}
                        icon={<Crosshair size={18} strokeWidth={1.5} />}
                        title="Recenter"
                        shortcut="3"
                    />

                    <ToolbarButtonWithTooltip
                        active={props.isLoadingClusters}
                        onClick={props.onRefresh}
                        icon={<RefreshCw size={18} strokeWidth={1.5} className={cn(props.isLoadingClusters && "animate-spin")} />}
                        title="Refresh"
                    />

                    <div className="w-px h-6 bg-gray-200 mx-0.5" />

                    <SettingsDropdown
                        currentStrategy={props.currentStrategy}
                        onStrategyChange={props.onStrategyChange}
                        currentProjection={props.currentProjection}
                        onProjectionChange={props.onProjectionChange}
                        currentOverlap={props.currentOverlap}
                        onOverlapChange={props.onOverlapChange}
                        jitterAmount={props.jitterAmount}
                        onJitterAmountChange={props.onJitterAmountChange}
                        explosionEnabled={props.explosionEnabled}
                        onExplosionEnabledChange={props.onExplosionEnabledChange}
                        isBuilt={isBuilt}
                        handleBuild={handleBuild}
                    />
                </div>
            </div>

            {/* Top Right - Stats Dropdown */}
            {(props.totalImages !== undefined || props.clusterCount !== undefined) && (
                <div className="fixed top-6 right-4 z-50">
                    <StatsDropdown
                        totalImages={props.totalImages}
                        clusterCount={props.clusterCount}
                        onFocusImage={props.onFocusImage}
                    />
                </div>
            )}

        </TooltipProvider>
    );
}
