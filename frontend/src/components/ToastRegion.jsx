import React from 'react';
import { Check, AlertCircle, Info, X } from 'lucide-react';

const ICON = {
  success: <Check size={13} strokeWidth={2.8} />,
  error:   <AlertCircle size={13} strokeWidth={2.5} />,
  info:    <Info size={13} strokeWidth={2.5} />,
};

export default function ToastRegion({ toasts, dismiss }) {
  if (!toasts.length) return null;
  return (
    <div className="toast-region" role="status" aria-live="polite">
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.type} ${t.leaving ? 'leaving' : ''}`}>
          <span className="toast-icon" aria-hidden="true">{ICON[t.type]}</span>
          <span className="toast-message">{t.message}</span>
          <button
            type="button"
            className="toast-dismiss"
            onClick={() => dismiss(t.id)}
            aria-label="Dismiss"
          >
            <X size={12} strokeWidth={2.5} />
          </button>
        </div>
      ))}
    </div>
  );
}
