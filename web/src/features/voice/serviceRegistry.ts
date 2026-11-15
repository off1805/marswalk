/**
 * Registre des singletons de V1 (composition root).
 *
 * Principe D : les singletons sont créés ici et injectés dans les hooks.
 * Les hooks ne les instancient pas directement.
 * Les tests remplacent les singletons via `__set*ForTest`.
 */
import { BrowserSpeechRecognizer, type ISpeechRecognizer } from "./speechRecognition";
import { createSynthesizer, type ISpeechSynthesizer } from "./speechSynthesis";

let _recognizer: ISpeechRecognizer | null = null;
let _synthesizer: ISpeechSynthesizer | null = null;

export function getRecognizer(): ISpeechRecognizer {
  if (!_recognizer) {
    // en-US : reconnaissance et wake word en anglais
    _recognizer = new BrowserSpeechRecognizer("en-US");
  }
  return _recognizer;
}

export function getSynthesizer(): ISpeechSynthesizer {
  if (!_synthesizer) {
    _synthesizer = createSynthesizer(navigator.onLine ? "online" : "offline");
  }
  return _synthesizer;
}

/** Pour les tests uniquement. */
export function __setRecognizerForTest(r: ISpeechRecognizer): void {
  _recognizer = r;
}
export function __setSynthesizerForTest(s: ISpeechSynthesizer): void {
  _synthesizer = s;
}
