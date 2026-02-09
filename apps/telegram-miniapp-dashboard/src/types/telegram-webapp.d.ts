// Minimal typings for Telegram WebApp SDK.
// Expand these types as you start using more of the SDK.
// Ref: https://core.telegram.org/bots/webapps

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

export type TelegramWebApp = {
  initData: string;
  initDataUnsafe: unknown;
  version: string;
  platform: string;
  colorScheme?: "light" | "dark";
  themeParams?: Record<string, string>;

  ready: () => void;
  expand: () => void;
  close: () => void;

  // Send data to the bot (delivered as message.web_app_data on the bot side).
  // Docs: https://core.telegram.org/bots/webapps#initializing-mini-apps
  sendData?: (data: string) => void;

  // Optional helper in many versions; keep it loose.
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
};
