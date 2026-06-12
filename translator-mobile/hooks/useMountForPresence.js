import { useEffect, useRef, useState } from "react";

/** Tracks mount state for enter/exit banners without putting `mounted` in effect deps. */
export function useMountForPresence(show) {
  const [mounted, setMounted] = useState(Boolean(show));
  const mountedRef = useRef(mounted);
  mountedRef.current = mounted;

  useEffect(() => {
    if (show) {
      setMounted((current) => (current ? current : true));
      return undefined;
    }
    if (!mountedRef.current) return undefined;
    return undefined;
  }, [show]);

  return { mounted, mountedRef, setMounted };
}
