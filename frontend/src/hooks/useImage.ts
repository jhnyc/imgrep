import { useEffect, useRef, useState } from 'react';

export function useImage(url: string | undefined | null, crossOrigin?: string) {
  const [image, setImage] = useState<HTMLImageElement | undefined>(undefined);
  const [status, setStatus] = useState<'loading' | 'loaded' | 'failed'>('loading');
  const imageRef = useRef<HTMLImageElement | undefined>(undefined);

  useEffect(() => {
    if (!url) return;

    const img = document.createElement('img');

    if (crossOrigin) {
      img.crossOrigin = crossOrigin;
    }

    const onload = () => {
      setImage(img);
      setStatus('loaded');
    };

    const onerror = () => {
      setImage(undefined);
      setStatus('failed');
    };

    img.addEventListener('load', onload);
    img.addEventListener('error', onerror);
    img.src = url;
    imageRef.current = img;

    return () => {
      img.removeEventListener('load', onload);
      img.removeEventListener('error', onerror);
    };
  }, [url, crossOrigin]);

  return [image, status] as const;
}
