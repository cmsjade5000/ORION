import React from "react";
import ReactDOM from "react-dom/client";
import { MiniApp } from "./app";
import "./styles.css";

if (!(window as typeof window & { __ORION_FILE_MODE__?: boolean }).__ORION_FILE_MODE__) {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <MiniApp />
    </React.StrictMode>
  );
}
