import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

export async function startMockServer(): Promise<void> {
  await setupWorker(...handlers).start({
    onUnhandledRequest: ({ url }, print) => {
      const path = new URL(url).pathname;
      if (path.startsWith("/api") || path.startsWith("/ws")) print.warning();
    },
  });
}
