import { useCallback, useEffect, useState } from "react";

async function readDiagnostics(apiUrl) {
  const base = String(apiUrl || "").trim().replace(/\/+$/, "");
  if (!base) return { status: "offline", data: null };
  try {
    const response = await fetch(`${base}/diagnostics`);
    if (!response.ok) {
      return { status: "offline", data: null };
    }
    const data = await response.json();
    return { status: data?.ready ? "online" : "checking", data };
  } catch {
    return { status: "offline", data: null };
  }
}

export function useMobileDiagnostics(apiUrl) {
  const [diagnostics, setDiagnostics] = useState(null);
  const [diagnosticsStatus, setDiagnosticsStatus] = useState("checking");

  const loadDiagnostics = useCallback(async () => {
    setDiagnosticsStatus("checking");
    const result = await readDiagnostics(apiUrl);
    setDiagnostics(result.data);
    setDiagnosticsStatus(result.status);
    return result.data;
  }, [apiUrl]);

  useEffect(() => {
    loadDiagnostics();
  }, [loadDiagnostics]);

  return { diagnostics, diagnosticsStatus, loadDiagnostics };
}
