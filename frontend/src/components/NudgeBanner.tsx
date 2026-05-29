import { useState } from 'react'
import type { Nudge } from '../lib/api'

export function NudgeBanner({ nudges }: { nudges: Nudge[] }) {
  const [dismissed, setDismissed] = useState<Set<string>>(() => {
    try {
      const stored = sessionStorage.getItem('dismissed-nudges')
      return stored ? new Set(JSON.parse(stored)) : new Set()
    } catch {
      return new Set()
    }
  })

  const dismiss = (id: string) => {
    const next = new Set(dismissed).add(id)
    setDismissed(next)
    try { sessionStorage.setItem('dismissed-nudges', JSON.stringify([...next])) } catch {}
  }

  const visible = nudges.filter(n => !dismissed.has(n.id))
  if (visible.length === 0) return null

  return (
    <div className="nudge-list">
      {visible.map(n => (
        <div key={n.id} className="nudge">
          <span className="nudge-icon">{n.icon}</span>
          <span className="nudge-text">{n.text}</span>
          <button className="nudge-dismiss" onClick={() => dismiss(n.id)} aria-label="Dismiss">✕</button>
        </div>
      ))}
    </div>
  )
}
