type EventCallback = () => void;

type TelegramBottomButton = {
  show(): void;
  hide(): void;
  enable?(): void;
  disable?(): void;
  setText(text: string): void;
  onClick(cb: EventCallback): void;
  offClick(cb: EventCallback): void;
  showProgress?(leaveActive?: boolean): void;
  hideProgress?(): void;
};

type TelegramBackButton = {
  show(): void;
  hide(): void;
  onClick(cb: EventCallback): void;
  offClick(cb: EventCallback): void;
};

type TelegramHaptic = {
  impactOccurred?(style: "light" | "medium" | "heavy" | "rigid" | "soft"): void;
  notificationOccurred?(type: "error" | "success" | "warning"): void;
  selectionChanged?(): void;
};

export type TelegramWebAppLike = {
  initData?: string;
  colorScheme?: string;
  isExpanded?: boolean;
  isFullscreen?: boolean;
  themeParams?: Record<string, string>;
  safeAreaInset?: Record<string, number>;
  contentSafeAreaInset?: Record<string, number>;
  MainButton?: TelegramBottomButton;
  BackButton?: TelegramBackButton;
  HapticFeedback?: TelegramHaptic;
  ready?(): void;
  expand?(): void;
  requestFullscreen?(): Promise<void> | void;
  onEvent?(event: string, cb: EventCallback): void;
  offEvent?(event: string, cb: EventCallback): void;
  close?(): void;
};

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebAppLike };
  }
}

export function getTelegramWebApp(): TelegramWebAppLike | null {
  return window.Telegram?.WebApp ?? null;
}

export function applyTelegramTheme(tg: TelegramWebAppLike | null) {
  if (!tg) return;
  const root = document.documentElement;
  const theme = tg.themeParams || {};
  Object.entries(theme).forEach(([key, value]) => {
    if (!value) return;
    root.style.setProperty(`--tg-theme-${key.replace(/_/g, "-")}`, value);
  });
  root.style.setProperty("--tg-color-scheme", tg.colorScheme || "dark");
}

export function applySafeAreaInsets(tg: TelegramWebAppLike | null) {
  if (!tg) return;
  const inset = tg.contentSafeAreaInset || tg.safeAreaInset || {};
  const root = document.documentElement;
  root.style.setProperty("--safe-top", `${inset.top || 0}px`);
  root.style.setProperty("--safe-right", `${inset.right || 0}px`);
  root.style.setProperty("--safe-bottom", `${inset.bottom || 0}px`);
  root.style.setProperty("--safe-left", `${inset.left || 0}px`);
}

export async function prepareTelegramShell(tg: TelegramWebAppLike | null) {
  if (!tg) return;
  tg.ready?.();
  tg.expand?.();
  applyTelegramTheme(tg);
  applySafeAreaInsets(tg);
}

export function vibrateSelection(tg: TelegramWebAppLike | null) {
  tg?.HapticFeedback?.selectionChanged?.();
}

export function vibrateImpact(tg: TelegramWebAppLike | null, style: "light" | "medium" | "heavy" = "light") {
  tg?.HapticFeedback?.impactOccurred?.(style);
}

export function vibrateNotice(tg: TelegramWebAppLike | null, type: "error" | "success" | "warning") {
  tg?.HapticFeedback?.notificationOccurred?.(type);
}
