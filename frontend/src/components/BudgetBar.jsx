const SEGMENTS = [
  { key: 'system', label: 'Case file', className: 'bg-ink' },
  { key: 'pinned', label: 'Pinned', className: 'bg-highlight' },
  { key: 'kept', label: 'Recent lines', className: 'bg-ink-soft/70' },
  { key: 'trimmed', label: 'Trimmed', className: 'bg-redpen/60' },
]

export default function BudgetBar({ report }) {
  const { budget, tokens_before: before, tokens_after: after, decisions } = report
  const sums = Object.fromEntries(SEGMENTS.map((s) => [s.key, 0]))
  for (const d of decisions) if (d.status in sums) sums[d.status] += d.final_tokens
  const scale = Math.max(before, budget, after)
  const pct = (n) => `${(n / scale) * 100}%`
  const over = after > budget

  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span>
          <span className={`font-type text-2xl tabular-nums ${over ? 'text-redpen' : ''}`}>{after}</span>
          <span className="text-graphite"> of {budget} tokens sent</span>
        </span>
        <span className="text-graphite tabular-nums">{before} in full</span>
      </div>

      <div className="relative mt-2">
        {/* Whole transcript, faint */}
        <div className="h-1.5 rounded-full bg-rule" style={{ width: pct(before) }} />
        {/* What actually gets sent */}
        <div className="mt-1 flex h-4 overflow-hidden rounded-sm bg-paper-shade">
          {SEGMENTS.map((s) =>
            sums[s.key] ? (
              <div
                key={s.key}
                title={`${s.label}: ${sums[s.key]} tokens`}
                className={`${s.className} transition-[width] duration-300`}
                style={{ width: pct(sums[s.key]) }}
              />
            ) : null,
          )}
        </div>
        {/* Budget line */}
        <div className="absolute -top-1 bottom-[-4px] w-0.5 bg-redpen" style={{ left: pct(budget) }} aria-hidden />
      </div>

      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-graphite">
        {SEGMENTS.filter((s) => sums[s.key]).map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span className={`inline-block h-2.5 w-2.5 rounded-[2px] ${s.className}`} />
            {s.label} {sums[s.key]}
          </li>
        ))}
        <li className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-0.5 bg-redpen" />
          Budget
        </li>
      </ul>
    </div>
  )
}
