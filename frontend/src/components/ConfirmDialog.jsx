import { useEffect, useId, useRef, useState } from "react";

export default function ConfirmDialog({ title, children, match, action = "Delete", busy, error, onConfirm, onClose }) {
  const ref = useRef(null);
  const titleId = useId();
  const [text, setText] = useState("");
  useEffect(() => {
    const previous = document.activeElement;
    const dialog = ref.current;
    dialog.showModal();
    return () => { dialog.close(); previous?.focus?.(); };
  }, []);
  return (
    <dialog ref={ref} className="management-dialog" aria-labelledby={titleId} onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
      <form onSubmit={event => { event.preventDefault(); if (!busy && (!match || text === match)) onConfirm(text); }}>
        <h2 id={titleId}>{title}</h2>
        <div className="dialog-description">{children}</div>
        {match && <label className="management-field">Type “{match}” to confirm<input autoComplete="off" autoFocus value={text} onChange={event => setText(event.target.value)} disabled={busy} /></label>}
        {error && <p className="management-error" role="alert">{error}</p>}
        <div className="management-actions">
          <button type="button" className="btn ghost" disabled={busy} onClick={onClose}>Cancel</button>
          <button type="submit" className="btn management-danger" disabled={busy || (match && text !== match)}>{busy ? "Working…" : action}</button>
        </div>
      </form>
    </dialog>
  );
}
