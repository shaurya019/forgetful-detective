import { useEffect, useState } from 'react'
import Lobby from './components/Lobby'
import CaseRoom from './components/CaseRoom'

const readHash = () => window.location.hash.replace(/^#\/?/, '') || null

export default function App() {
  const [sessionId, setSessionId] = useState(readHash)

  useEffect(() => {
    const onHash = () => setSessionId(readHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const open = (id) => {
    window.location.hash = id ? `/${id}` : ''
    setSessionId(id)
  }

  return sessionId ? <CaseRoom key={sessionId} sessionId={sessionId} onLeave={() => open(null)} /> : <Lobby onOpen={open} />
}
