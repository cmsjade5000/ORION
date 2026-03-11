type AsyncTask<T> = () => Promise<T>;

export class BoundedExecutor {
  private readonly maxConcurrent: number;
  private inFlight = 0;
  private readonly waiters: Array<() => void> = [];

  constructor(maxConcurrent: number) {
    this.maxConcurrent = Math.max(1, Math.trunc(maxConcurrent));
  }

  private async acquire(): Promise<void> {
    if (this.inFlight < this.maxConcurrent) {
      this.inFlight += 1;
      return;
    }

    await new Promise<void>((resolve) => {
      this.waiters.push(resolve);
    });
    this.inFlight += 1;
  }

  private release(): void {
    this.inFlight = Math.max(0, this.inFlight - 1);
    const next = this.waiters.shift();
    if (next) next();
  }

  async run<T>(task: AsyncTask<T>): Promise<T> {
    await this.acquire();
    try {
      return await task();
    } finally {
      this.release();
    }
  }
}

export class ChatTaskQueue {
  private readonly tails = new Map<number, Promise<unknown>>();

  enqueue<T>(chatId: number, task: AsyncTask<T>): Promise<T> {
    const previous = this.tails.get(chatId) ?? Promise.resolve();
    const next = previous.catch(() => undefined).then(task);
    this.tails.set(
      chatId,
      next.finally(() => {
        if (this.tails.get(chatId) === next) {
          this.tails.delete(chatId);
        }
      })
    );
    return next;
  }
}
