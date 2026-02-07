import { useQuery } from '@tanstack/react-query';
import { ExternalLink, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, queryKeys } from '../api/client';

const CLUSTER_COLORS = [
  '#ffb3b3', '#ffd4a8', '#fff3b0', '#c7f5bd',
  '#a8e6f5', '#b3d4ff', '#d4b3ff', '#ffb3e6',
];

export default function ImageViewer() {
  const [imageId, setImageId] = useState<number | null>(null);

  useEffect(() => {
    const handleOpenViewer = (e: CustomEvent) => {
      setImageId(e.detail.imageId);
    };

    window.addEventListener('open-image-viewer', handleOpenViewer as EventListener);
    return () => {
      window.removeEventListener('open-image-viewer', handleOpenViewer as EventListener);
    };
  }, []);

  const { data: details, isLoading } = useQuery({
    queryKey: queryKeys.imageDetails(imageId!),
    queryFn: () => api.getImageDetails(imageId!),
    enabled: !!imageId,
  });

  const handleClose = () => {
    setImageId(null);
  };

  const openInFinder = () => {
    if (details?.file_path) {
      console.log('Opening:', details.file_path);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  if (!imageId) return null;

  return (
    <div
      className="fixed inset-0 z-[60] bg-black/30 backdrop-blur-sm flex items-center justify-center p-6"
      onClick={handleClose}
    >
      <div
        className="relative flex flex-col md:flex-row w-full max-w-5xl max-h-[85vh] bg-white rounded-2xl overflow-hidden animate-scale-in"
        style={{ boxShadow: '0 0 0 1px rgba(0,0,0,0.08), 0 24px 64px rgba(0,0,0,0.15)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 z-10 w-9 h-9 flex items-center justify-center bg-white/90 hover:bg-gray-100 backdrop-blur rounded-lg text-gray-500 hover:text-gray-800 transition-all"
          style={{ boxShadow: '0 0 0 1px rgba(0,0,0,0.08), 0 2px 8px rgba(0,0,0,0.08)' }}
          title="Close (Esc)"
        >
          <X size={18} strokeWidth={1.5} />
        </button>

        {/* Image Area */}
        <div className="flex-1 bg-gray-50 flex items-center justify-center p-8 overflow-hidden relative">
          {isLoading ? (
            <div className="flex flex-col items-center gap-4">
              <div className="w-8 h-8 border-2 border-gray-200 border-t-blue-500 rounded-full animate-spin" />
            </div>
          ) : details ? (
            <div className="relative w-full h-full flex items-center justify-center">
              <img
                src={api.getOriginalImageUrl(imageId)}
                alt={details.file_name}
                className="max-w-full max-h-full object-contain rounded-lg"
                style={{ boxShadow: '0 4px 24px rgba(0,0,0,0.12)' }}
              />
            </div>
          ) : (
            <div className="text-red-500">Failed to load content</div>
          )}
        </div>

        {/* Sidebar Details */}
        {details && (
          <div className="w-full md:w-72 bg-white p-6 flex flex-col overflow-y-auto border-l border-gray-100">
            <div className="mb-5">
              <span className="bg-blue-100 text-blue-600 px-2.5 py-1 rounded-lg text-xs font-semibold">
                Asset Details
              </span>
            </div>

            <h2 className="text-lg font-semibold text-gray-800 mb-5 leading-tight break-words">
              {details.file_name}
            </h2>

            <div className="space-y-5 flex-1">
              <div>
                <label className="text-xs font-medium text-gray-400 uppercase tracking-wide block mb-1">Dimensions</label>
                <p className="text-sm text-gray-700">
                  {details.width && details.height
                    ? `${details.width} × ${details.height} px`
                    : 'Unknown'}
                </p>
              </div>

              <div>
                <label className="text-xs font-medium text-gray-400 uppercase tracking-wide block mb-1">Cluster</label>
                <div className="flex items-center gap-2">
                  <span
                    className="w-3 h-3 rounded-full"
                    style={{
                      backgroundColor: details.cluster_label !== null
                        ? CLUSTER_COLORS[details.cluster_label % CLUSTER_COLORS.length]
                        : '#e5e5e5'
                    }}
                  />
                  <p className="text-sm text-gray-700">
                    {details.cluster_label !== null
                      ? `Cluster #${details.cluster_label}`
                      : 'Unclassified'}
                  </p>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-gray-400 uppercase tracking-wide block mb-1">Path</label>
                <div className="p-2.5 bg-gray-50 border border-gray-200 rounded-xl text-xs font-mono break-all text-gray-600 select-all">
                  {details.file_path}
                </div>
              </div>
            </div>

            <div className="mt-6">
              <button
                onClick={openInFinder}
                className="w-full py-2.5 bg-gray-900 hover:bg-gray-800 text-white rounded-xl transition-all flex items-center justify-center gap-2 font-medium text-sm"
              >
                <ExternalLink size={16} strokeWidth={1.5} />
                Reveal in Finder
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
