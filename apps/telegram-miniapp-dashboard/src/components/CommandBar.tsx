import { useEffect, useRef, useState } from "react";

export default function CommandBar(props: {
  placeholder?: string;
  disabled?: boolean;
  // Return true to clear the input (accepted), false to keep it (rejected/failed).
  onSubmit: (text: string) => Promise<boolean> | boolean;
}) {
  const [value, setValue] = useState("");
  const [sending, setSending] = useState(false);
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto-grow textarea (helps on mobile; avoids cramped single-line input).
  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(140, Math.max(36, el.scrollHeight))}px`;
  }, [value]);

  return (
    <form
      className="commandBar"
      onSubmit={async (e) => {
        e.preventDefault();
        if (props.disabled || sending) return;
        const text = value.trim();
        if (!text) return;
        setSending(true);
        try {
          const ok = await props.onSubmit(text);
          if (ok) setValue("");
        } finally {
          setSending(false);
        }
      }}
    >
      <textarea
        className="input"
        ref={taRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={props.placeholder}
        disabled={Boolean(props.disabled) || sending}
        autoCapitalize="sentences"
        autoCorrect="on"
        rows={1}
        onKeyDown={(e) => {
          // Enter sends; Shift+Enter inserts newline.
          // Avoid interfering with IME composition.
          const anyE = e as any;
          if (anyE.isComposing) return;
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            const form = e.currentTarget.form as HTMLFormElement | null;
            if (!form) return;
            if (typeof form.requestSubmit === "function") form.requestSubmit();
            else form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
          }
        }}
      />
      <button className="button" type="submit" disabled={Boolean(props.disabled) || sending}>
        {sending ? "Sending" : "Send"}
      </button>
    </form>
  );
}
