import type { SearchResult } from '../lib/api'

interface Props {
  results: SearchResult[]
  query: string
  loading: boolean
}

function sourceLabel(path: string): string {
  if (path.startsWith('notion/tasks'))    return 'Task'
  if (path.startsWith('notion/schedule')) return 'Event'
  return 'Note'
}

function sourceIcon(path: string): string {
  if (path.startsWith('notion/tasks'))    return '✓'
  if (path.startsWith('notion/schedule')) return '◷'
  return '◈'
}

export function SearchResults({ results, query, loading }: Props) {
  if (loading) return <p className="results-empty">Searching…</p>
  if (!query)  return null
  if (!results.length) return <p className="results-empty">No results for "{query}"</p>

  return (
    <ul className="results-list">
      {results.map((r) => (
        <li key={r.path} className="result-item">
          <div className="result-meta">
            <span className="result-source">{sourceIcon(r.path)} {sourceLabel(r.path)}</span>
            <span className="result-path">{r.path}</span>
            <span className="result-score">{r.score.toFixed(2)}</span>
          </div>
          <h3 className="result-title">{r.title}</h3>
          <p
            className="result-snippet"
            dangerouslySetInnerHTML={{ __html: r.snippet }}
          />
        </li>
      ))}
    </ul>
  )
}
