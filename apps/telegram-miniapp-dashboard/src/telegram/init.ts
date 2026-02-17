import type { TelegramWebApp } from "../types/telegram-webapp";

export type TelegramContext = {
  webApp: TelegramWebApp;
  initData: string;
  platform: string;
  version: string;
  startParam?: string;
};

/**
 * Initializes Telegram WebApp if present.
 *
 * Notes:
 * - In local browser/dev, `window.Telegram` will likely be undefined.
 * - `initData` is signed by Telegram. The backend should later verify it.
 */
export function initTelegram(): TelegramContext | null {
  const webApp = window.Telegram?.WebApp;
  if (!webApp) return null;

  // Let Telegram know we’re ready to render and ask for more viewport.
  webApp.ready();
  webApp.expand();

  // Optional cosmetics.
  try {
    webApp.setHeaderColor?.("#0b1020");
    webApp.setBackgroundColor?.("#0b1020");
  } catch {
    // Ignore SDK differences between versions.
  }

  return {
    webApp,
    initData: webApp.initData || "",
    startParam: (() => {
      try {
        const unsafe = webApp.initDataUnsafe as any;
        if (unsafe && typeof unsafe.start_param === "string") return unsafe.start_param;
      } catch {
        // ignore
      }
      return "";
    })(),
    platform: webApp.platform,
    version: webApp.version,
  };
}
