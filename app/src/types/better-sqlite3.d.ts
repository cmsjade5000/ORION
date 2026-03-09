declare module "better-sqlite3" {
  type BindParameter = string | number | bigint | null | Uint8Array;

  interface Statement<TRow = unknown> {
    run(...params: BindParameter[]): { changes: number; lastInsertRowid: bigint | number };
    get(...params: BindParameter[]): TRow;
    all(...params: BindParameter[]): TRow[];
  }

  interface Database {
    pragma(source: string): unknown;
    exec(source: string): this;
    prepare<TRow = unknown>(source: string): Statement<TRow>;
    transaction<T extends (...args: never[]) => unknown>(fn: T): T;
  }

  interface DatabaseConstructor {
    new (path: string): Database;
  }

  const Database: DatabaseConstructor;
  export default Database;
}
