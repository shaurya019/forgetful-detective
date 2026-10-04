export default function CaseFile({ session }) {
  const c = session.case
  return (
    <details className="group rounded-sm bg-paper-shade text-ink shadow-[0_1px_0_var(--color-rule)]" open={session.player_turns === 0}>
      <summary className="flex cursor-pointer list-none items-baseline justify-between gap-4 px-5 py-3">
        <span className="font-semibold">Case file</span>
        <span className="text-sm text-graphite group-open:hidden">{c.time_window}</span>
      </summary>
      <div className="grid gap-6 border-t border-rule px-5 pb-5 pt-4 sm:grid-cols-2">
        <div className="space-y-3 text-[15px] leading-relaxed">
          <p>{c.crime}</p>
          <p>
            <span className="text-graphite">Where </span>
            {c.location}
            <br />
            <span className="text-graphite">When </span>
            {c.time_window}
          </p>
          <p className="border-l-2 border-ink/30 pl-3">{c.suspect_profile}</p>
          <p className="text-graphite">
            {c.detective_name}. {c.detective_style}
          </p>
        </div>
        <ol className="space-y-3 font-type text-[15px]">
          {c.evidence.map((e, i) => (
            <li key={e.item} className="grid grid-cols-[2rem_1fr]">
              <span className="text-graphite">E{i + 1}</span>
              <span>
                <span className="font-bold">{e.item}.</span> {e.detail}
              </span>
            </li>
          ))}
        </ol>
      </div>
    </details>
  )
}
