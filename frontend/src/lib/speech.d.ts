// The Web Speech API is not yet in TypeScript's standard DOM lib.
// These minimal declarations are enough for our useVoice hook.

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList
}
interface SpeechRecognitionErrorEvent extends Event {
  error: string
}
interface SpeechRecognition extends EventTarget {
  lang: string
  interimResults: boolean
  continuous: boolean
  onstart:  ((this: SpeechRecognition, ev: Event) => void) | null
  onend:    ((this: SpeechRecognition, ev: Event) => void) | null
  onerror:  ((this: SpeechRecognition, ev: SpeechRecognitionErrorEvent) => void) | null
  onresult: ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => void) | null
  start(): void
  stop(): void
}
declare var SpeechRecognition: { new(): SpeechRecognition }

interface Window {
  SpeechRecognition:       typeof SpeechRecognition
  webkitSpeechRecognition: typeof SpeechRecognition
}

interface SpeechRecognitionResultList {
  length: number
  item(index: number): SpeechRecognitionResult
  [index: number]: SpeechRecognitionResult
}
interface SpeechRecognitionResult {
  length: number
  isFinal: boolean
  item(index: number): SpeechRecognitionAlternative
  [index: number]: SpeechRecognitionAlternative
}
interface SpeechRecognitionAlternative {
  transcript: string
  confidence: number
}
