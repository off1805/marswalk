/**
 * Abstraction de la Web Speech API (reconnaissance vocale).
 *
 * Deux modes selon l'usage :
 *   - wake-word (en-US, continu)  : écoute permanente du mot « Nebula »
 *   - commandes  (en-US, single)  : écoute d'une commande après réveil
 *
 * Principe D : le code dépend de ISpeechRecognizer, jamais de
 * window.SpeechRecognition directement.
 */

export interface ISpeechRecognizer {
  start(): void;
  stop(): void;
  onResult(cb: (transcript: string, isFinal: boolean) => void): void;
  onError(cb: (error: string) => void): void;
  onEnd(cb: () => void): void;
  isSupported(): boolean;
}

// Types inline — SpeechRecognition est absent de lib.dom.d.ts standard.
interface SpeechRecognitionResult {
  readonly isFinal: boolean;
  0: { transcript: string };
}
interface SpeechRecognitionEvent extends Event {
  readonly results: { [i: number]: SpeechRecognitionResult; length: number };
}
interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
}
interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onresult: ((e: SpeechRecognitionEvent) => void) | null;
  onerror: ((e: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}
interface SpeechRecognitionConstructor { new(): SpeechRecognitionInstance; }

export class BrowserSpeechRecognizer implements ISpeechRecognizer {
  private rec: SpeechRecognitionInstance | null = null;

  /** lang — langue d'écoute ; pour V1 : toujours "en-US". */
  constructor(private readonly lang = "en-US") {}

  isSupported(): boolean {
    return "SpeechRecognition" in window || "webkitSpeechRecognition" in window;
  }

  private get instance(): SpeechRecognitionInstance {
    if (!this.rec) {
      const w = window as unknown as {
        SpeechRecognition?: SpeechRecognitionConstructor;
        webkitSpeechRecognition?: SpeechRecognitionConstructor;
      };
      const SR = w.SpeechRecognition ?? w.webkitSpeechRecognition;
      if (!SR) throw new Error("Web Speech API not supported");
      this.rec = new SR();
      this.rec.continuous = false;
      this.rec.interimResults = true;
      this.rec.lang = this.lang;
      this.rec.maxAlternatives = 2;
    }
    return this.rec;
  }

  start(): void { this.instance.start(); }
  stop(): void  { this.rec?.stop(); }

  onResult(cb: (transcript: string, isFinal: boolean) => void): void {
    this.instance.onresult = (e) => {
      const result = e.results[e.results.length - 1];
      if (result) cb(result[0].transcript, result.isFinal);
    };
  }

  onError(cb: (error: string) => void): void {
    this.instance.onerror = (e) => cb(e.error);
  }

  onEnd(cb: () => void): void {
    this.instance.onend = cb;
  }
}

// ── Mock pour les tests ───────────────────────────────────────────────────────

export class MockSpeechRecognizer implements ISpeechRecognizer {
  private resultCb?: (t: string, f: boolean) => void;
  private errorCb?: (e: string) => void;
  private endCb?: () => void;

  isSupported() { return true; }
  start() { /* no-op */ }
  stop()  { /* no-op */ }
  onResult(cb: (t: string, f: boolean) => void) { this.resultCb = cb; }
  onError(cb: (e: string) => void) { this.errorCb = cb; }
  onEnd(cb: () => void) { this.endCb = cb; }

  emit(transcript: string, isFinal = true) {
    this.resultCb?.(transcript, isFinal);
    if (isFinal) this.endCb?.();
  }
  emitError(error: string) { this.errorCb?.(error); }
}
