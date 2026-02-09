import { useState } from "react";

export default function CommandBar(props: {
  placeholder?: string;
  onSubmit: (text: string) => Promise<void> | void;
}) {
  const [value, setValue] = useState("");

  return (
    <form
      className="commandBar"
      onSubmit={async (e) => {
        e.preventDefault();
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
        autoCapitalize="sentences"
        autoCorrect="on"
      />
      <button className="button" type="submit">
        Send
      </button>
    </form>
  );
}
