import { useEffect, useState } from 'react'
import { fetchToday, getBriefing, type TodayData, type Task, type ScheduleEvent, type OnThisDayNote } from '../lib/api'

const PRIORITY_COLOR: Record<string, string> = {
  High:   'var(--accent)',
  Medium: '#f59e0b',
  Low:    'var(--text-dim)',
}

const TYPE_ICON: Record<string, string> = {
  Class:    '◑',
  Study:    '◈',
  Personal: '◇',
  Meeting:  '◎',
}

const TYPE_COLOR: Record<string, string> = {
  Class:    'var(--accent)',
  Study:    '#a78bfa',
  Personal: '#34d399',
  Meeting:  '#f59e0b',
}

function formatDue(iso: string): string {
  const d = new Date(iso + 'T00:00:00')
  const today = new Date()
  const diff = Math.ceil((d.getTime() - today.setHours(0,0,0,0)) / 86400000)
  if (diff < 0)  return `${Math.abs(diff)}d overdue`
  if (diff === 0) return 'today'
  if (diff === 1) return 'tomorrow'
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function TaskCard({ task }: { task: Task }) {
  const color = PRIORITY_COLOR[task.priority ?? ''] ?? 'var(--text-dim)'
  const isOverdue = task.due_date ? new Date(task.due_date) < new Date() : false
  return (
    <div className="card task-card">
      <div className="card-left" style={{ background: color }} />
      <div className="card-body">
        <span className="card-title">{task.name}</span>
        <div className="card-meta">
          {task.priority && (
            <span className="badge" style={{ color, borderColor: color }}>
              {task.priority}
            </span>
          )}
          {task.status && (
            <span className="badge badge--muted">{task.status}</span>
          )}
          {task.due_date && (
            <span className={`badge ${isOverdue ? 'badge--warn' : 'badge--muted'}`}>
              {formatDue(task.due_date)}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function EventCard({ event }: { event: ScheduleEvent }) {
  const icon  = TYPE_ICON[event.type ?? '']  ?? '◌'
  const color = TYPE_COLOR[event.type ?? ''] ?? 'var(--text-dim)'
  return (
    <div className="card event-card">
      <span className="event-icon" style={{ color }}>{icon}</span>
      <div className="card-body">
        <span className="card-title">{event.name}</span>
        {event.notes && <span className="card-sub">{event.notes}</span>}
        {event.type && (
          <span className="badge badge--muted" style={{ borderColor: color, color }}>{event.type}</span>
        )}
      </div>
    </div>
  )
}

function OnThisDayCard({ note }: { note: OnThisDayNote }) {
  const folder = note.path.split('/')[0]
  return (
    <div className="card on-this-day-card">
      <div className="card-left" style={{ background: 'var(--text-dim)' }} />
      <div className="card-body">
        <span className="card-title">{note.title}</span>
        <div className="card-meta">
          {note.year && <span className="badge badge--muted">{note.year}</span>}
          <span className="badge badge--muted">{folder}</span>
        </div>
      </div>
    </div>
  )
}

export function TodayPanel() {
  const [data, setData]         = useState<TodayData | null>(null)
  const [onThisDay, setOnThisDay] = useState<OnThisDayNote[]>([])
  const [error, setError]       = useState(false)

  useEffect(() => {
    fetchToday().then(setData).catch(() => setError(true))
    getBriefing()
      .then(b => setOnThisDay(b.on_this_day))
      .catch(() => {})
  }, [])

  if (error) return (
    <div className="today-error">
      Couldn't reach the backend. Is it running on port 8000?
    </div>
  )
  if (!data) return (
    <div className="today-loading">
      <div className="spinner" />
      Loading your day…
    </div>
  )

  return (
    <div className={`today-grid ${onThisDay.length > 0 ? 'today-grid--3col' : ''}`}>
      {/* ── Schedule ── */}
      <section className="today-section">
        <header className="section-header">
          <span className="section-title">Today's schedule</span>
          <span className="section-count">{data.schedule.length}</span>
        </header>
        {data.schedule.length === 0
          ? <p className="empty-state">Nothing on the calendar — enjoy the breathing room.</p>
          : data.schedule.map(e => <EventCard key={e.id} event={e} />)
        }
      </section>

      {/* ── Tasks ── */}
      <section className="today-section">
        <header className="section-header">
          <span className="section-title">Top tasks</span>
          <span className="section-count">{data.top_tasks.length}</span>
        </header>
        {data.top_tasks.length === 0
          ? <p className="empty-state">All clear.</p>
          : data.top_tasks.map(t => <TaskCard key={t.id} task={t} />)
        }

        {/* Neglected */}
        {data.neglected && (
          <>
            <header className="section-header" style={{ marginTop: '24px' }}>
              <span className="section-title" style={{ color: '#f59e0b' }}>⚑ Don't forget</span>
            </header>
            <div className="neglected-card">
              <TaskCard task={data.neglected} />
            </div>
          </>
        )}
      </section>

      {/* ── On this day ── */}
      {onThisDay.length > 0 && (
        <section className="today-section">
          <header className="section-header">
            <span className="section-title">On this day</span>
            <span className="section-count">{onThisDay.length}</span>
          </header>
          {onThisDay.map(n => <OnThisDayCard key={n.path} note={n} />)}
        </section>
      )}
    </div>
  )
}
