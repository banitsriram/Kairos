/**
 * useVoice — thin React hook over the browser Web Speech API.
 *
 * Two modes:
 *   'search'  — transcribes speech and calls onResult with the text (transient).
 *   'capture' — same transcription, but caller decides what to do with the text
 *               (e.g. POST to /capture). No audio is stored by this hook.
 *
 * Why Web Speech API vs server-side Whisper?
 * WSA is free, on-device (Chrome/Safari send to Google/Apple — see ROADMAP for
 * the self-hosted Whisper upgrade path if privacy matters later). Zero latency,
 * zero infra, perfect for a first pass.
 *
 * Browser support: Chrome/Edge = full. Safari = partial. Firefox = none.
 * The hook returns supported=false on unsupported browsers so the UI can hide
 * the mic button gracefully.
 */
import { useCallback, useRef, useState } from 'react'

export type VoiceState = 'idle' | 'listening' | 'error'

interface UseVoiceOptions {
  onResult: (text: string) => void
  onError?: (msg: string) => void
  continuous?: boolean
}

export function useVoice({ onResult, onError, continuous = false }: UseVoiceOptions) {
  const [state, setState] = useState<VoiceState>('idle')
  const recognitionRef = useRef<SpeechRecognition | null>(null)

  const supported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  const start = useCallback(() => {
    if (!supported) return
    const SR = window.SpeechRecognition ?? window.webkitSpeechRecognition
    const rec = new SR()
    rec.lang = 'en-US'
    rec.interimResults = false
    rec.continuous = continuous

    rec.onstart  = () => setState('listening')
    rec.onerror  = (e: SpeechRecognitionErrorEvent) => {
      setState('error')
      onError?.(e.error)
    }
    rec.onend    = () => setState('idle')
    rec.onresult = (e: SpeechRecognitionEvent) => {
      const text = Array.from(e.results)
        .map((r: SpeechRecognitionResult) => r[0].transcript)
        .join(' ')
        .trim()
      if (text) onResult(text)
    }

    recognitionRef.current = rec
    rec.start()
  }, [supported, continuous, onResult, onError])

  const stop = useCallback(() => {
    recognitionRef.current?.stop()
  }, [])

  return { state, start, stop, supported }
}
