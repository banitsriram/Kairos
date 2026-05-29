import { useEffect, useState } from 'react'
import { getBriefing, type Briefing } from '../lib/api'

function StreakBadge({ count, bonus }: { count: number; bonus: boolean }) {
  return (
    <div className="briefing-streak">
      <span className={`streak-flame ${bonus ? 'streak-flame--gold' : ''}`}>🔥</span>
      <span className="streak-count">{count}</span>
      <span className="streak-label">day{count !== 1 ? 's' : ''}</span>
    </div>
  )
}

export function BriefingCard() {
  const [data, setData] = useState<Briefing | null>(null)

  useEffect(() => {
    getBriefing().then(setData).catch(() => {/* silent — briefing is non-critical */})
  }, [])

  if (!data) return null

  const { greeting, context, streak, on_this_day } = data

  return (
    <div className="briefing-card">
      <div className="briefing-main">
        <p className="briefing-greeting">"{greeting}"</p>
        <StreakBadge count={streak.count} bonus={streak.bonus} />
      </div>

      <div className="briefing-pills">
        {context.next_event && (
          <span className="briefing-pill">
            <span className="briefing-pill-icon">📅</span>
            {context.next_event.name}
          </span>
        )}
        {context.overdue_count > 0 && (
          <span className="briefing-pill briefing-pill--warn">
            <span className="briefing-pill-icon">⚠</span>
            {context.overdue_count} overdue
          </span>
        )}
        {on_this_day.length > 0 && (
          <span className="briefing-pill">
            <span className="briefing-pill-icon">📝</span>
            {on_this_day.length} note{on_this_day.length !== 1 ? 's' : ''} from this day
          </span>
        )}
      </div>
    </div>
  )
}
