/**
 * CommandPalette — opens on Cmd+K (or Ctrl+K).
 *
 * Two modes toggled by the tab bar:
 *   Search  — live search across vault + Notion
 *   Capture — speak or type a thought, saves it to the vault via POST /capture
 *
 * Architecture note: the palette is a controlled component — the parent
 * owns `open` state and passes `onClose`. This pattern is common in React
 * because it lets parents (and keyboard handlers) control visibility without
 * needing to reach into the child.
 */
import { useEffect, useRef, useState } from 'react'
import { capture, search, type SearchResult } from '../lib/api'
import { useDebounce } from '../lib/useDebounce'
import { useVoice } from '../lib/useVoice'
import { SearchResults } from './SearchResults'

type Mode = 'search' | 'capture'

interface Props {
  open: boolean
  onClose: () => void
}

export function CommandPalette({ open, onClose }: Props) {
  const [mode, setMode]         = useState<Mode>('search')
  const [query, setQuery]       = useState('')
  const [results, setResults]   = useState<SearchResult[]>([])
  const [loading, setLoading]   = useState(false)
  const [captureText, setCaptureText] = useState('')
  const [captureStatus, setCaptureStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const inputRef = useRef<HTMLInputElement & HTMLTextAreaElement>(null)
  const debouncedQuery = useDebounce(query, 250)

  // Focus input when palette opens
  useEffect(() => {
    if (open) {
      setQuery('')
      setResults([])
      setCaptureText('')
      setCaptureStatus('idle')
      setTimeout(() => inputRef.current?.focus(), 30)
    }
  }, [open])

  // Live search
  useEffect(() => {
    if (mode !== 'search' || !debouncedQuery.trim()) {
      setResults([])
      return
    }
    setLoading(true)
    search(debouncedQuery)
      .then((r) => setResults(r.results))
      .catch(() => setResults([]))
      .finally(() => setLoading(false))
  }, [debouncedQuery, mode])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  const { state: voiceState, start: startVoice, stop: stopVoice, supported: voiceSupported } =
    useVoice({
      onResult: (text) => setCaptureText((prev) => (prev ? prev + ' ' + text : text)),
    })

  async function handleCapture() {
    if (!captureText.trim()) return
    setCaptureStatus('saving')
    try {
      await capture(captureText.trim())
      setCaptureStatus('saved')
      setTimeout(() => { setCaptureStatus('idle'); setCaptureText(''); onClose() }, 1200)
    } catch {
      setCaptureStatus('error')
    }
  }

  if (!open) return null

  return (
    <div className="palette-backdrop" onClick={onClose}>
      <div className="palette" onClick={(e) => e.stopPropagation()}>
        {/* Mode tabs */}
        <div className="palette-tabs">
          <button
            className={`palette-tab ${mode === 'search' ? 'palette-tab--active' : ''}`}
            onClick={() => setMode('search')}
          >
            Search
          </button>
          <button
            className={`palette-tab ${mode === 'capture' ? 'palette-tab--active' : ''}`}
            onClick={() => setMode('capture')}
          >
            Capture
          </button>
          <span className="palette-hint">ESC to close</span>
        </div>

        {mode === 'search' && (
          <>
            <input
              ref={inputRef as React.RefObject<HTMLInputElement>}
              className="palette-input"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search vault + Notion…"
              spellCheck={false}
              autoComplete="off"
            />
            <div className="palette-results">
              <SearchResults results={results} query={query} loading={loading} />
            </div>
          </>
        )}

        {mode === 'capture' && (
          <div className="capture-pane">
            <textarea
              ref={inputRef as React.RefObject<HTMLTextAreaElement>}
              className="capture-input"
              value={captureText}
              onChange={(e) => setCaptureText(e.target.value)}
              placeholder="What's on your mind? Type or use the mic…"
              rows={5}
            />
            <div className="capture-actions">
              {voiceSupported && (
                <button
                  className={`mic-btn ${voiceState === 'listening' ? 'mic-btn--active' : ''}`}
                  onClick={voiceState === 'listening' ? stopVoice : startVoice}
                >
                  {voiceState === 'listening' ? '◉ Listening…' : '⊙ Speak'}
                </button>
              )}
              <button
                className="capture-save"
                onClick={handleCapture}
                disabled={!captureText.trim() || captureStatus === 'saving'}
              >
                {captureStatus === 'saving' ? 'Saving…'
                  : captureStatus === 'saved'  ? '✓ Saved'
                  : captureStatus === 'error'  ? 'Error — retry'
                  : 'Save to vault'}
              </button>
            </div>
            <p className="capture-note">
              Saves as a new timestamped note tagged #voice-capture. Never overwrites existing notes.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
