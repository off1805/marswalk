import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "@/app/App";
import { registry } from "@/app/registry";
import "@/shared/tokens.css";

async function boot() {
  if (import.meta.env.VITE_MOCK) {
    const { startMockServer } = await import("@/shared/mocks/browser");
    await startMockServer();
  }
  await Promise.all(registry.map((f) => f.setup?.()));
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void boot();
