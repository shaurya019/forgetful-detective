import { useState } from 'react'
import { useSaveMemory } from '../hooks/queries'
import BudgetBar from './BudgetBar'

const STRATEGIES = [
  {
    value: 'fit_to_budget',
    label: 'Fit to budget',
    hint: 'Keeps whole question-and-answer pairs, newest first, until the budget is full. Trims the latest line if it has to.',
  },
  {
    value: 'drop_oldest',
    label: 'Drop oldest',
    hint: 'Forgets one line at a time, oldest first, until everything fits. Can separate an answer from its question.',
  },
  {
    value: 'system_plus_last_n',
    label: 'Case file plus last N',
    hint: 'Keeps the case file, pinned lines and the last N lines. Counts lines, not tokens, so it can run over.',
  },
]

const COUNT_LABELS = { kept: 'kept', pinned: 'pinned', trimmed: 'trimmed', dropped: 'forgotten' }

function Ledger({ report, messages }) {
  const [showAll, setShowAll] = useState(false)
  const byId = Object.fromEntries(messages.map((m) => [m.id, m]))
  const rows = report.decisions.filter((d) => d.role !== 'system' && (showAll || d.status === 'dropped' || d.status === 'trimmed'))
  const counts = report.decisions.reduce((acc, d) => ({ ...acc, [d.status]: (acc[d.status] ?? 0) + 1 }), {})

  return (
    <div>
      <p className="text-sm text-graphite">
        {Object.entries(COUNT_LABELS)
          .filter(([k]) => counts[k])
          .map(([k, label]) => `${counts[k]} ${label}`)
          .join(', ')}
      </p>
      <ol className="mt-2 max-h-72 space-y-2 overflow-y-auto pr-1 text-sm">
        {rows.map((d) => (
          <li key={d.id} className="grid grid-cols-[2.25rem_1fr_auto] gap-x-2">
            <span className="text-right font-type tabular-nums text-graphite">{Number(d.id)}</span>
            <span className="min-w-0">
              <span className={`block truncate font-type ${d.status === 'dropped' ? 'struck' : ''}`}>
                {d.role === 'assistant' ? 'Q. ' : 'A. '}
                {byId[d.id]?.content}
              </span>
              <span className="block text-xs text-graphite">{d.reason}</span>
            </span>
            <span className="tabular-nums text-graphite">{d.tokens}</span>
          </li>
        ))}
        {rows.length === 0 && <li className="text-graphite">Nothing forgotten yet. The whole interview fits.</li>}
      </ol>
      <button onClick={() => setShowAll((s) => !s)} className="mt-2 text-sm text-ink-soft underline underline-offset-2">
        {showAll ? 'Show only forgotten and trimmed lines' : 'Show every line'}
      </button>
    </div>
  )
}

export default function MemoryPanel({ sessionId, draft, setDraft, saved, previewing, preview, messages, recalled }) {
  const save = useSaveMemory(sessionId)
  if (!draft) return null
  const report = preview.data
  const set = (patch) => setDraft((d) => ({ ...d, ...patch }))
  const active = STRATEGIES.find((s) => s.value === draft.strategy)

  return (
    <div className="space-y-6 rounded-sm bg-paper p-5 text-ink">
      <div>
        <h2 className="text-lg font-semibold">The detective's memory</h2>
        <p className="mt-1 text-sm leading-relaxed text-graphite">
          Change the settings to see which lines would be forgotten. Pinned lines and the case file are never dropped.
        </p>
      </div>

      <fieldset>
        <legend className="text-sm font-semibold">Strategy</legend>
        <div className="mt-2 grid grid-cols-3 gap-1 rounded-sm bg-paper-shade p-1">
          {STRATEGIES.map((s) => (
            <label
              key={s.value}
              className={`cursor-pointer rounded-[2px] px-2 py-2 text-center text-sm leading-tight transition has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ink ${
                draft.strategy === s.value ? 'bg-ink text-paper' : 'hover:bg-rule/60'
              }`}
            >
              <input
                type="radio"
                name="strategy"
                value={s.value}
                checked={draft.strategy === s.value}
                onChange={() => set({ strategy: s.value })}
                className="sr-only"
              />
              {s.label}
            </label>
          ))}
        </div>
        <p className="mt-2 text-sm leading-relaxed text-graphite">{active?.hint}</p>
      </fieldset>

      <div className="space-y-4">
        <label className="block">
          <span className="flex justify-between text-sm">
            <span className="font-semibold">Token budget</span>
            <span className="font-type tabular-nums">{draft.budget_tokens}</span>
          </span>
          <input
            type="range"
            min={200}
            max={4000}
            step={50}
            value={draft.budget_tokens}
            onChange={(e) => set({ budget_tokens: Number(e.target.value) })}
            className="mt-1 w-full accent-ink"
          />
        </label>
        {draft.strategy === 'system_plus_last_n' && (
          <label className="block">
            <span className="flex justify-between text-sm">
              <span className="font-semibold">Last N lines</span>
              <span className="font-type tabular-nums">{draft.last_n}</span>
            </span>
            <input
              type="range"
              min={0}
              max={40}
              value={draft.last_n}
              onChange={(e) => set({ last_n: Number(e.target.value) })}
              className="mt-1 w-full accent-ink"
            />
          </label>
        )}
      </div>

      {report && (
        <div className={preview.isPlaceholderData ? 'opacity-60 transition-opacity' : 'transition-opacity'}>
          <BudgetBar report={report} />
          {report.warnings.map((w) => (
            <p key={w} className="mt-2 text-sm text-redpen">
              {w}
            </p>
          ))}
        </div>
      )}
      {preview.error && <p className="text-sm text-redpen">{preview.error.message}</p>}

      <div className="flex flex-wrap items-center gap-3">
        {previewing ? (
          <>
            <button
              onClick={() => save.mutate(draft)}
              disabled={save.isPending}
              className="rounded-sm bg-ink px-4 py-2 text-sm font-semibold text-paper hover:bg-ink-soft disabled:opacity-50"
            >
              {save.isPending ? 'Applying…' : 'Apply to the detective'}
            </button>
            <button onClick={() => setDraft(saved)} className="text-sm text-ink-soft underline underline-offset-2">
              Discard changes
            </button>
          </>
        ) : (
          <p className="text-sm text-graphite">This is what the detective will see on your next answer.</p>
        )}
        {save.error && <p className="text-sm text-redpen">{save.error.message}</p>}
      </div>

      <div>
        <h3 className="text-sm font-semibold">Pulled from cold storage last turn</h3>
        {recalled.length ? (
          <ul className="mt-2 space-y-2">
            {recalled.map((r) => (
              <li key={r.msg_id} className="border-l-2 border-highlight pl-3 font-type text-sm">
                <span className="text-graphite">#{Number(r.msg_id)} </span>
                {r.role === 'assistant' ? 'Q. ' : 'A. '}
                {r.content}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-sm text-graphite">
            Nothing yet. Forgotten lines go to Pinecone, and the detective searches them every time you answer.
          </p>
        )}
      </div>

      {report && (
        <div>
          <h3 className="text-sm font-semibold">Why lines were forgotten</h3>
          <div className="mt-1">
            <Ledger report={report} messages={messages} />
          </div>
        </div>
      )}
    </div>
  )
}
