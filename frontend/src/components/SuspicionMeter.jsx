export default function SuspicionMeter({ value = 0 }) {
  const v = Math.max(0, Math.min(100, value))
  const hot = v >= 75
  return (
    <div className="flex items-center gap-3" role="meter" aria-valuenow={v} aria-valuemin={0} aria-valuemax={100} aria-label="Suspicion">
      <span className="text-sm text-paper/70">Suspicion</span>
      <div className="relative h-2.5 w-32 overflow-hidden rounded-full bg-black/30 sm:w-44">
        <div
          className={`h-full transition-[width] duration-700 ease-out ${hot ? 'bg-redpen' : 'bg-paper'}`}
          style={{ width: `${v}%` }}
        />
        {[25, 50, 75].map((t) => (
          <span key={t} className="absolute top-0 h-full w-px bg-wall-deep/70" style={{ left: `${t}%` }} />
        ))}
      </div>
      <span className={`w-8 text-right font-type tabular-nums ${hot ? 'text-highlight' : ''}`}>{v}</span>
    </div>
  )
}
