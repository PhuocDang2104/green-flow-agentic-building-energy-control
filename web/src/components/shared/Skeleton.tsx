/**
 * Shimmer skeleton placeholder. A muted block with a light gradient sweeping
 * across it (animate-shimmer) — used everywhere a resource/chart is loading.
 */
export default function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-lg bg-surface-muted ${className}`}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer
        bg-gradient-to-r from-transparent via-white/70 to-transparent" />
    </div>
  );
}
