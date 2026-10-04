import { useEffect, useMemo, useState } from 'react'
import { useContextPreview, useDebounced, useSession } from '../hooks/queries'
import CaseFile from './CaseFile'
import MemoryPanel from './MemoryPanel'
import SuspicionMeter from './SuspicionMeter'
import Transcript from './Transcript'

const sameMemory = (a, b) =>
  !!a && !!b && a.strategy === b.strategy && +a.budget_tokens === +b.budget_tokens && +a.last_n === +b.last_n

export default function CaseRoom({ sessionId, onLeave }) {
  const { data, isLoading, error } = useSession(sessionId)
  const saved = data?.session.memory
  const [draft, setDraft] = useState(null)

  useEffect(() => {
    if (saved && !draft) setDraft(saved)
  }, [saved, draft])

  const debounced = useDebounced(draft, 180)
  const preview = useContextPreview(sessionId, debounced)
  const decisions = useMemo(
    () => Object.fromEntries((preview.data?.decisions ?? []).map((d) => [d.id, d])),
    [preview.data],
  )

  // Ids the detective pulled back from cold storage on its most recent turn.
  const lastRecall = useMemo(() => {
    const last = [...(data?.messages ?? [])].reverse().find((m) => m.role === 'assistant' && m.context)
    return last?.context?.recalled ?? []
  }, [data])

  if (isLoading) return <p className="p-8 font-type text-paper/70">Pulling the file…</p>
  if (error)
    return (
      <div className="p-8">
        <p className="text-highlight">{error.message}</p>
        <button onClick={onLeave} className="mt-4 underline">
          Back to case files
        </button>
      </div>
    )

  const { session, messages } = data
  const previewing = !sameMemory(draft, saved)

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-20 border-b border-black/20 bg-wall-deep/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <button onClick={onLeave} className="text-sm text-paper/70 hover:text-paper">
            Case files
          </button>
          <h1 className="min-w-0 flex-1 truncate font-type text-lg">{session.title}</h1>
          <SuspicionMeter value={session.suspicion} />
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div className="min-w-0 space-y-4">
          <CaseFile session={session} />
          <Transcript
            session={session}
            messages={messages}
            decisions={decisions}
            recalled={lastRecall}
            previewing={previewing}
          />
        </div>
        <aside className="lg:sticky lg:top-20 lg:max-h-[calc(100dvh-6rem)] lg:overflow-y-auto">
          <MemoryPanel
            sessionId={sessionId}
            draft={draft}
            setDraft={setDraft}
            saved={saved}
            previewing={previewing}
            preview={preview}
            messages={messages}
            recalled={lastRecall}
          />
        </aside>
      </div>
    </div>
  )
}
