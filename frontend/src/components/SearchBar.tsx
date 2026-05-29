import { useRef } from 'react'
import { useVoice } from '../lib/useVoice'

interface Props {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}

export function SearchBar({ value, onChange, placeholder }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)

  const { state, start, stop, supported } = useVoice({
    onResult: (text) => onChange(text),
  })

  const listening = state === 'listening'

  return (
    <div className={`search-bar ${listening ? 'search-bar--listening' : ''}`}>
      <span className="search-icon">⌕</span>
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? 'Search everything…'}
        spellCheck={false}
        autoComplete="off"
      />
      {value && (
        <button className="search-clear" onClick={() => onChange('')} aria-label="Clear">
          ×
        </button>
      )}
      {supported && (
        <button
          className={`mic-btn ${listening ? 'mic-btn--active' : ''}`}
          onMouseDown={listening ? stop : start}
          aria-label={listening ? 'Stop' : 'Voice search'}
          title={listening ? 'Tap to stop' : 'Search by voice'}
        >
          {listening
            ? <span className="mic-pulse">⬤</span>
            : '⊙'
          }
        </button>
      )}
    </div>
  )
}
