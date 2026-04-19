import { useMemo } from "react";
import { useLocation } from "react-router-dom";

/** IDE segment from `/admin/ide-agents/:ide/...` */
export function useRouteIdeFromPath(): string | null {
  const { pathname } = useLocation();
  return useMemo(() => {
    const m = pathname.match(/^\/admin\/ide-agents\/([^/]+)/);
    return m ? m[1].toLowerCase() : null;
  }, [pathname]);
}
