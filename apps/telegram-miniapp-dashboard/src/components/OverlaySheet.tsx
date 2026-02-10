import { useEffect } from "react";

export default function OverlaySheet(props: {
  open: boolean;
  title: string;
  subtitle?: string | null;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    if (!props.open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") props.onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [props.open, props.onClose]);

  useEffect(() => {
    if (!props.open) return;
    // Prevent background scroll while the sheet is open.
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [props.open]);

  if (!props.open) return null;

  return (
    <div className="overlayRoot" role="dialog" aria-modal="true" aria-label={props.title}>
      <button type="button" className="overlayScrim" aria-label="Close" onClick={props.onClose} />
      <div className="overlaySheet">
        <div className="overlayHeader">
          <div className="overlayHeadText">
            <div className="overlayTitle">{props.title}</div>
            {props.subtitle ? <div className="overlaySubtitle">{props.subtitle}</div> : null}
          </div>
          <button type="button" className="overlayClose" onClick={props.onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="overlayBody">{props.children}</div>
      </div>
    </div>
  );
}

