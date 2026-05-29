export interface SearchResult {
  path: string
  title: string
  snippet: string
  score: number
}

export interface Task {
  id: string
  name: string
  status: string | null
  priority: string | null
  due_date: string | null
  url: string | null
}

export interface ScheduleEvent {
  id: string
  name: string
  date: string | null
  type: string | null
  notes: string
  url: string | null
}

export interface TodayData {
  date: string
  schedule: ScheduleEvent[]
  top_tasks: Task[]
  neglected: Task | null
}

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export async function search(q: string): Promise<{ results: SearchResult[] }> {
  return get(`/search?q=${encodeURIComponent(q)}`)
}

export async function fetchToday(): Promise<TodayData> {
  return get('/today')
}

export async function capture(text: string): Promise<{ path: string; title: string }> {
  const res = await fetch(BASE + '/capture', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}
