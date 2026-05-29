import { useEffect, useState } from 'react'
import { CommandPalette } from './components/CommandPalette'
import { SearchBar } from './components/SearchBar'
import { SearchResults } from './components/SearchResults'
import { TodayPanel } from './components/TodayPanel'
import { search, type SearchResult } from './lib/api'
import { useDebounce } from './lib/useDebounce'
import { applyTheme, getPeriodLabel, type Period } from './lib/theme'

function Clock() {
  const [time, setTime] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <span className="clock">
      {time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
    </span>
  )
}

function DateLine() {
  const d = new Date()
  return (
    <span className="dateline">
      {d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
    </span>
  )
}

export default function App() {
  const [query, setQuery]             = useState('')
  const [results, setResults]         = useState<SearchResult[]>([])
  const [searching, setSearching]     = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [period, setPeriod]           = useState<Period>('morning')
  const debouncedQuery                = useDebounce(query, 250)

  useEffect(() => {
    const apply = () => setPeriod(applyTheme())
    apply()
    const id = setInterval(apply, 60_000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    if (!debouncedQuery.trim()) { setResults([]); return }
    setSearching(true)
    search(debouncedQuery)
      .then((r) => setResults(r.results))
      .catch(() => setResults([]))
      .finally(() => setSearching(false))
  }, [debouncedQuery])

  const inSearch = query.trim().length > 0

  return (
    <div className="app">
      {/* ── Top bar ── */}
      <header className="topbar">
        <span className="logo">Kairos</span>
        <div className="topbar-right">
          <Clock />
          <button className="kbd-badge" onClick={() => setPaletteOpen(true)} title="Command palette">
            ⌘K
          </button>
        </div>
      </header>

      <main className="main">
        {/* ── Hero ── */}
        <section className="hero">
          <div className="hero-greeting">
            <h1>{getPeriodLabel(period)}</h1>
            <DateLine />
          </div>

          <SearchBar
            value={query}
            onChange={setQuery}
            placeholder="Search vault, tasks, notes…"
          />

          {/* Feature hints — only shown when not searching */}
          {!inSearch && (
            <div className="feature-hints">
              <button className="hint-pill" onClick={() => setPaletteOpen(true)}>
                <span className="hint-icon">⌘</span> Command palette
              </button>
              <button className="hint-pill" onClick={() => { setPaletteOpen(true) }}>
                <span className="hint-icon">⊙</span> Voice capture
              </button>
              <span className="hint-pill hint-pill--static">
                <span className="hint-icon">◈</span> Vault + Notion unified
              </span>
            </div>
          )}
        </section>

        {/* ── Content ── */}
        {inSearch ? (
          <section className="search-view">
            <p className="search-label">
              {searching ? 'Searching…' : `Results for "${query}"`}
            </p>
            <SearchResults results={results} query={query} loading={searching} />
          </section>
        ) : (
          <TodayPanel />
        )}
      </main>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  )
}
