declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready: () => void;
        expand: () => void;
        requestFullscreen?: () => void;
        hideKeyboard?: () => void;
        setHeaderColor?: (color: string) => void;
        setBackgroundColor?: (color: string) => void;
        initDataUnsafe?: {
          user?: {
            id?: number;
            first_name?: string;
            username?: string;
          };
        };
      };
    };
  }
}

export interface LocalUser {
  id: number;
  firstName: string;
  username: string;
  mode: "telegram" | "local";
}

export function resolveWebAppUser(): LocalUser {
  if (typeof window === "undefined") {
    return {
      id: 0,
      firstName: "Operator",
      username: "local",
      mode: "local"
    };
  }

  const webApp = window.Telegram?.WebApp;
  if (!webApp?.initDataUnsafe?.user) {
    return {
      id: 0,
      firstName: "Operator",
      username: "local",
      mode: "local"
    };
  }

  const user = webApp.initDataUnsafe.user;
  return {
    id: user.id ?? 0,
    firstName: user.first_name ?? "Operator",
    username: user.username ?? "telegram",
    mode: "telegram"
  };
}

export function initTelegramWebApp(): void {
  if (typeof window === "undefined") {
    return;
  }
  const webApp = window.Telegram?.WebApp;
  if (!webApp) {
    return;
  }

  webApp.ready();
  webApp.expand();
  webApp.setHeaderColor?.("#07111f");
  webApp.setBackgroundColor?.("#07111f");
  webApp.requestFullscreen?.();
}

export function dismissTelegramKeyboard(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.Telegram?.WebApp?.hideKeyboard?.();
}
