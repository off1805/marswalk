/**
 * Abstraction de l'API Web Speech (reconnaissance vocale).
 *
 * Principe D (Dependency Inversion) : le code applicatif dépend de
 * `ISpeechRecognizer`, pas de `window.SpeechRecognition` directement.
 * Les tests injectent `MockSpeechRecognizer` sans navigateur.
 *
 * Principe S : wrappeur uniquement — pas de logique de commande ici.
 *
 * Note : `SpeechRecognition` n'est pas dans `lib.dom.d.ts` standard.
 * On utilise des types inline pour éviter une dépendance supplémentaire.
 */

export interface ISpeechRecognizer {
  start(): void;
  stop(): void;
  onResult(cb: (transcript: string, isFinal: boolean) => void): void;
  onError(cb: (error: string) => void): void;
  onEnd(cb: () => void): void;
  isSupported(): boolean;
}

// Types inline pour l'API Web Speech (non standard, absent de lib.dom.d.ts)
interface SpeechRecognitionResult {
  readonly isFinal: boolean;
  0: { transcript: string };
}
interface SpeechRecognitionEvent extends Event {
  readonly results: { [index: number]: SpeechRecognitionResult; length: number };
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
interface SpeechRecognitionConstructor {
  new(): SpeechRecognitionInstance;
}

/** Implémentation réelle utilisant la Web Speech API du navigateur. */
export class BrowserSpeechRecognizer implements ISpeechRecognizer {
  private rec: SpeechRecognitionInstance | null = null;

  constructor(private readonly lang = "fr-FR") {}

  isSupported(): boolean {
    return (
      "SpeechRecognition" in window || "webkitSpeechRecognition" in window
    );
  }

  private get instance(): SpeechRecognitionInstance {
    if (!this.rec) {
      const w = window as unknown as {
        SpeechRecognition?: SpeechRecognitionConstructor;
        webkitSpeechRecognition?: SpeechRecognitionConstructor;
      };
      const SR = w.SpeechRecognition ?? w.webkitSpeechRecognition;
      if (!SR) throw new Error("Web Speech API non supportée");
      this.rec = new SR();
      this.rec.continuous = false;
      this.rec.interimResults = true;
      this.rec.lang = this.lang;
      this.rec.maxAlternatives = 1;
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

/** Implémentation de test — injectable sans navigateur. */
export class MockSpeechRecognizer implements ISpeechRecognizer {
  private resultCb?: (t: string, f: boolean) => void;
  private errorCb?: (e: string) => void;
  private endCb?: () => void;

  isSupported() { return true; }
  start() { /* no-op */ }
  stop() { /* no-op */ }
  onResult(cb: (t: string, f: boolean) => void) { this.resultCb = cb; }
  onError(cb: (e: string) => void) { this.errorCb = cb; }
  onEnd(cb: () => void) { this.endCb = cb; }

  /** Simule un résultat final (pour les tests). */
  emit(transcript: string, isFinal = true) {
    this.resultCb?.(transcript, isFinal);
    if (isFinal) this.endCb?.();
  }

  /** Simule une erreur (pour les tests). */
  emitError(error: string) {
    this.errorCb?.(error);
  }
}
