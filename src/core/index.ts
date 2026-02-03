import fs from "fs";
import path from "path";

/**
 * Load working memory from memory/WORKING.md if it exists.
 * Returns the file contents as a string, or empty string if missing/unreadable.
 */
export function loadWorkingMemory(): string {
  const filePath = path.resolve(process.cwd(), "memory/WORKING.md");
  try {
    return fs.readFileSync(filePath, "utf-8");
  } catch (err) {
    console.warn(
      `Could not read working memory from ${filePath}: ${(err as Error).message}`
    );
    return "";
  }
}

/**
 * Working memory loaded at startup.
 */
export const workingMemory = loadWorkingMemory();
