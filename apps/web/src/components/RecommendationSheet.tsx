import {useEffect, useRef} from "react";
import type {KeyboardEvent, MouseEvent, ReactNode} from "react";

export function RecommendationSheet({onClose, children}: {onClose: () => void; children: ReactNode}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const backdropPress = useRef(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.showModal();
    closeRef.current?.focus();
    return () => {
      if (dialog.open) dialog.close();
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, []);

  function isBackdrop(event: MouseEvent<HTMLDialogElement>) {
    if (event.target !== event.currentTarget) return false;
    const bounds = event.currentTarget.getBoundingClientRect();
    return event.clientX < bounds.left || event.clientX > bounds.right
      || event.clientY < bounds.top || event.clientY > bounds.bottom;
  }

  function keepFocusInside(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== "Tab") return;
    const focusable = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
      'button:not([disabled]), a[href], summary, input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )).filter(element => !element.hidden);
    if (focusable.length === 0) return;
    const first = focusable[0]; const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last.focus();}
    else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first.focus();}
  }

  return <dialog ref={dialogRef} className="recommendation-sheet" aria-labelledby="recommendation-sheet-title"
    onCancel={event => {event.preventDefault(); onClose();}} onKeyDown={keepFocusInside}
    onPointerDown={event => {backdropPress.current = isBackdrop(event);}}
    onClick={event => {if (backdropPress.current && isBackdrop(event)) onClose(); backdropPress.current = false;}}>
    <div className="recommendation-sheet-header">
      <h3 id="recommendation-sheet-title">Why this response is recommended</h3>
      <button ref={closeRef} type="button" onClick={onClose}>Close</button>
    </div>
    <div className="recommendation-sheet-body">{children}</div>
  </dialog>;
}
