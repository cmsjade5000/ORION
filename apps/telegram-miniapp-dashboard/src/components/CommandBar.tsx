import { useState } from "react";

export default function CommandBar(props: {
  placeholder?: string;
  disabled?: boolean;
  onSubmit: (text: string) => Promise<void> | void;
}) {
  const [value, setValue] = useState("");

  return (
    <form
      className="commandBar"
      onSubmit={async (e) => {
        e.preventDefault();
        if (props.disabled) return;
        const text = value.trim();
        if (!text) return;
        setValue("");
        await props.onSubmit(text);
      }}
    >
      <input
        className="input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={props.placeholder}
        disabled={Boolean(props.disabled)}
        autoCapitalize="sentences"
        autoCorrect="on"
      />
      <button className="button" type="submit" disabled={Boolean(props.disabled)}>
        Send
      </button>
    </form>
  );
}
