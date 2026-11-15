/**
 * Registre des singletons de F7.
 *
 * Principe D (Dependency Inversion) : les singletons sont créés ici
 * (composition root du module) et injectés dans les hooks via des
 * accesseurs. Les hooks ne les instancient pas directement.
 *
 * L'initialisation est paresseuse — les singletons ne sont créés qu'à
 * la première utilisation, ce qui évite les effets de bord à l'import.
 */
import { OperationQueue, buildReplayHandlers } from "./operationQueue";

let _queue: OperationQueue | null = null;

/** Retourne le singleton `OperationQueue` (créé à la première demande). */
export function getQueue(): OperationQueue {
  if (!_queue) {
    _queue = new OperationQueue(localStorage, buildReplayHandlers());
  }
  return _queue;
}

/**
 * Remplace le singleton par une instance de test.
 * À utiliser uniquement dans les tests unitaires.
 */
export function __setQueueForTest(queue: OperationQueue): void {
  _queue = queue;
}
