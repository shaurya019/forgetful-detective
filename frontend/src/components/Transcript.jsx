import { useEffect, useRef, useState } from 'react'
import { useAnswer, usePin } from '../hooks/queries'

function MarginNote({ decision, message, recalled }) {
  const notes = []
  if (recalled) notes.push(<span key="r" className="text-ink">recalled</span>)
  if (!decision) return notes.length ? <>{notes}</> : null
  if (decision.status === 'dropped') {
    notes.push(
      <span key="d" className="text-redpen">
        forgotten
      </span>,
    )
    if (message.archived) notes.push(<span key="a">in cold storage</span>)
  }
  if (decision.status === 'trimmed') notes.push(<span key="t" className="text-redpen">trimmed</span>)
  if (decision.status === 'pinned') notes.push(<span key="p">pinned</span>)
  return <>{notes}</>
}

function Line({ message, decision, recalled, onPin, canPin }) {
  const isQ = message.role === 'assistant'
  const status = decision?.status
  const dropped = status === 'dropped'
  const pinned = message.pinned

  return (
    <li className="group grid grid-cols-[2.25rem_1.75rem_minmax(0,1fr)] gap-x-1 py-1.5 sm:grid-cols-[2.5rem_2rem_minmax(0,1fr)_7.5rem]">
      <span className="pt-0.5 text-right font-ui text-xs tabular-nums text-graphite">
        {message.pending ? '' : Number(message.id)}
      </span>
      <span className="font-bold">{isQ ? 'Q.' : 'A.'}</span>
      <div className="min-w-0">
        <p
          title={decision?.reason}
          className={`whitespace-pre-wrap leading-7 ${dropped ? 'struck' : ''} ${message.pending ? 'text-graphite' : ''}`}
        >
          <span className={pinned && !dropped ? 'marker' : ''}>{message.content}</span>
        </p>
        {message.contradiction && (
          <p className="mt-1 font-ui text-sm italic text-redpen">Caught: {message.contradiction}</p>
        )}
        {decision && dropped && <p className="mt-0.5 font-ui text-xs text-graphite sm:hidden">Forgotten: {decision.reason}</p>}
      </div>
      <div className="col-start-3 mt-1 flex flex-wrap items-start gap-x-3 font-ui text-xs text-graphite sm:col-start-4 sm:mt-0 sm:flex-col sm:gap-0.5 sm:pt-1">
        <MarginNote decision={decision} message={message} recalled={recalled} />
        {canPin && (
          <button
            onClick={() => onPin(message.id, !pinned)}
            className="text-ink-soft underline-offset-2 hover:underline sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100"
          >
            {pinned ? 'Unpin' : 'Pin'}
          </button>
        )}
      </div>
    </li>
  )
}

const ENDINGS = {
  arrested: (s) => `Arrested. The detective's suspicion reached ${s.suspicion}.`,
  released: (s) => `Released. Your story held for ${s.player_turns} answers.`,
}

export default function Transcript({ session, messages, decisions, recalled, previewing }) {
  const [text, setText] = useState('')
  const answer = useAnswer(session.session_id)
  const pin = usePin(session.session_id)
  const end = useRef(null)
  const lines = messages.filter((m) => m.role !== 'system')
  const recalledIds = new Set(recalled.map((r) => r.msg_id))
  const over = session.status !== 'active'

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [lines.length, answer.isPending])

  const submit = (e) => {
    e?.preventDefault()
    const content = text.trim()
    if (!content || answer.isPending || over) return
    answer.mutate(content, { onSuccess: () => setText('') })
  }

  return (
    <section className="rounded-sm bg-paper text-ink shadow-[0_18px_40px_-24px_rgba(0,0,0,0.6)]">
      <div className="flex items-baseline justify-between gap-4 border-b border-rule px-5 py-3">
        <h2 className="font-semibold">Transcript</h2>
        <p className="text-sm text-graphite">
          {previewing ? 'Showing a memory setting you haven’t applied' : 'Struck lines are outside the detective’s memory'}
        </p>
      </div>

      <ol className="ruled px-3 py-4 font-type text-[15.5px] sm:px-5">
        {lines.map((m) => (
          <Line
            key={m.id}
            message={m}
            decision={decisions[m.id]}
            recalled={recalledIds.has(m.id)}
            canPin={!m.pending}
            onPin={(msgId, pinned) => pin.mutate({ msgId, pinned })}
          />
        ))}
        {answer.isPending && (
          <li className="grid grid-cols-[2.25rem_1.75rem_1fr] gap-x-1 py-1.5 text-graphite sm:grid-cols-[2.5rem_2rem_1fr]">
            <span />
            <span className="font-bold">Q.</span>
            <span className="italic">The detective is checking the notebook…</span>
          </li>
        )}
        <li ref={end} aria-hidden />
      </ol>

      <div className="border-t border-rule px-5 py-4">
        {over ? (
          <p className="font-type text-lg">{ENDINGS[session.status]?.(session)}</p>
        ) : (
          <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <label className="sr-only" htmlFor="answer">
              Your answer
            </label>
            <textarea
              id="answer"
              rows={2}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) submit(e)
              }}
              placeholder="A. Answer the question. Keep your story straight."
              className="min-h-[3.5rem] flex-1 resize-y rounded-sm border border-rule bg-white/70 px-3 py-2 font-type text-[15.5px] text-ink placeholder:text-graphite focus:border-ink focus:outline-none"
            />
            <button
              type="submit"
              disabled={!text.trim() || answer.isPending}
              className="rounded-sm bg-ink px-5 py-2.5 font-semibold text-paper transition hover:bg-ink-soft disabled:opacity-40"
            >
              Answer
            </button>
          </form>
        )}
        {answer.error && <p className="mt-2 text-sm text-redpen">{answer.error.message}</p>}
        {pin.error && <p className="mt-2 text-sm text-redpen">Couldn't change the pin: {pin.error.message}</p>}
      </div>
    </section>
  )
}
