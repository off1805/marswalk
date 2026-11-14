import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router";
import { HabitatLayout, HudLayout, TabletLayout, Terrain3dLayout } from "./Layouts";
import { registry } from "./registry";
import { useShared, type Mode } from "@/shared/store";

export const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

const MODE_BY_PATH: Record<string, Mode> = { "/": "habitat", "/tablet": "tablet", "/hud": "hud", "/3d": "3d" };

function ModeSync() {
  const { pathname } = useLocation();
  const setMode = useShared((s) => s.setMode);
  useEffect(() => {
    setMode(MODE_BY_PATH[pathname] ?? "habitat");
  }, [pathname, setMode]);
  return null;
}

export function AppRoutes() {
  const extra = registry.flatMap((f) => f.routes).filter((r) => !(r.path in MODE_BY_PATH));
  return (
    <>
      <ModeSync />
      <Routes>
        <Route path="/" element={<HabitatLayout />} />
        <Route path="/tablet" element={<TabletLayout />} />
        <Route path="/hud" element={<HudLayout />} />
        <Route path="/3d" element={<Terrain3dLayout />} />
        {extra.map(({ path, component: C }) => (
          <Route key={path} path={path} element={<C />} />
        ))}
      </Routes>
    </>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
