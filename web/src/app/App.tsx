import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { BrowserRouter, Route, Routes, useLocation } from "react-router";
import { MapLayout, Terrain3dLayout } from "./Layouts";
import { registry } from "./registry";
import { SiteSync } from "./SitePicker";
import { useShared, type Mode } from "@/shared/store";

export const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

const MODE_BY_PATH: Record<string, Mode> = { "/": "map", "/3d": "3d" };

function ModeSync() {
  const { pathname } = useLocation();
  const setMode = useShared((s) => s.setMode);
  useEffect(() => {
    setMode(MODE_BY_PATH[pathname] ?? "map");
  }, [pathname, setMode]);
  return null;
}

export function AppRoutes() {
  const extra = registry.flatMap((f) => f.routes).filter((r) => !(r.path in MODE_BY_PATH));
  return (
    <>
      <ModeSync />
      <SiteSync />
      <Routes>
        <Route path="/" element={<MapLayout />} />
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
