import { useHealth, useOpenCase, useSessions } from '../hooks/queries'

const STATUS = { active: 'In progress', arrested: 'Arrested', released: 'Released' }

export default function Lobby({ onOpen }) {
  const health = useHealth()
  const sessions = useSessions()
  const newCase = useOpenCase({ onOpened: onOpen })
  const demo = useOpenCase({ demo: true, onOpened: onOpen })
  const openai = health.data?.openai
  const busy = newCase.isPending || demo.isPending

  return (
    <main className="mx-auto max-w-3xl px-5 pb-24 pt-16 sm:pt-24">
      <section className="font-type text-paper">
        <p className="text-sm text-paper/60">Interview room 2. Recording.</p>
        <h1 className="mt-6 text-5xl leading-[1.05] sm:text-7xl">
          Q. Where were you
          <br />
          on Thursday night?
        </h1>
        <p className="mt-8 max-w-[34rem] font-ui text-lg leading-relaxed text-paper/85">
          You're the suspect. The detective can only hold so much of the interview in its head at once. Whatever it
          forgets, you get away with. Unless something you say sends it back to its notebook.
        </p>
      </section>

      <div className="mt-10 flex flex-wrap gap-3">
        <button
          onClick={() => newCase.mutate()}
          disabled={!openai || busy}
          className="rounded-sm bg-paper px-5 py-3 font-semibold text-ink shadow-[3px_3px_0_var(--color-wall-deep)] transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {newCase.isPending ? 'Writing the case file…' : 'Open a new case'}
        </button>
        <button
          onClick={() => demo.mutate()}
          disabled={busy}
          className="rounded-sm border border-paper/40 px-5 py-3 font-semibold text-paper transition hover:border-paper hover:bg-wall-light/40 disabled:opacity-50"
        >
          {demo.isPending ? 'Loading…' : 'Load the demo interrogation'}
        </button>
      </div>

      <div className="mt-4 space-y-1 text-sm text-paper/70">
        {health.isError && <p className="text-highlight">Can't reach the API at /api. Start the backend on port 8000.</p>}
        {health.data && !openai && (
          <p>New cases need OPENAI_API_KEY on the server. The demo interrogation loads without it.</p>
        )}
        {health.data && !health.data.cold_storage && (
          <p>Pinecone isn't configured, so lines the detective forgets are gone for good.</p>
        )}
        {(newCase.error || demo.error) && (
          <p className="text-highlight">{(newCase.error || demo.error).message}</p>
        )}
      </div>

      <section className="mt-20">
        <h2 className="text-lg font-semibold">Case files</h2>
        {sessions.isLoading && <p className="mt-4 text-paper/60">Pulling files…</p>}
        {sessions.data?.length === 0 && (
          <p className="mt-4 text-paper/60">No cases yet. Load the demo to see a detective lose track of an alibi.</p>
        )}
        <ul className="mt-4 divide-y divide-paper/15 border-y border-paper/15">
          {sessions.data?.map((s) => (
            <li key={s.session_id}>
              <button
                onClick={() => onOpen(s.session_id)}
                className="grid w-full grid-cols-[1fr_auto] items-baseline gap-x-4 px-1 py-4 text-left transition hover:bg-wall-light/30"
              >
                <span className="font-type text-lg">{s.title}</span>
                <span className="text-sm tabular-nums text-paper/70">Suspicion {s.suspicion}</span>
                <span className="text-sm text-paper/60">
                  {STATUS[s.status]}, {s.player_turns} answers{s.is_demo ? ', demo' : ''}
                </span>
                <span className="text-sm text-paper/50">
                  {new Date(s.created_at * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </main>
  )
}
