import fs from 'fs';
import path from 'path';

import { searchQmd, getQmd, QmdResult } from './qmd_backend';

/**
 * Result entry from any memory backend.
 */
export interface MemoryResult {
  /** Source backend name: 'qmd' or 'memory' */
  source: 'qmd' | 'memory';
  /** Absolute file path or URI */
  path: string;
  /** Relevance score */
  score: number;
  /** Excerpt surrounding the match */
  excerpt: string;
}

/**
 * Search for a query across enabled memory backends (QMD workspace and daily memory files).
 * QMD backend results come first, followed by matches in the memory/ folder.
 * @param query The search query string.
 * @returns Array of MemoryResult entries.
 */
export async function memorySearch(query: string): Promise<MemoryResult[]> {
  const results: MemoryResult[] = [];

  // QMD backend (workspace notes)
  const qmdEntries: QmdResult[] = await searchQmd(query);
  for (const e of qmdEntries) {
    results.push({ source: 'qmd', path: e.path, score: e.score, excerpt: e.excerpt });
  }

  // Daily memory files in memory/ folder
  const memDir = path.resolve(process.cwd(), 'memory');
  if (fs.existsSync(memDir) && fs.statSync(memDir).isDirectory()) {
    const files = fs.readdirSync(memDir).filter((f) => f.endsWith('.md'));
    for (const file of files) {
      const filePath = path.join(memDir, file);
      const content = fs.readFileSync(filePath, 'utf8');
      const idx = content.toLowerCase().indexOf(query.toLowerCase());
      if (idx !== -1) {
        const start = Math.max(0, idx - 40);
        const end = Math.min(content.length, idx + query.length + 40);
        const excerpt = content.substring(start, end).replace(/\s+/g, ' ');
        results.push({ source: 'memory', path: filePath, score: 1, excerpt });
      }
    }
  }

  return results;
}

/**
 * Retrieve full content for a memory entry from the specified source.
 * @param source The backend source ('qmd' or 'memory').
 * @param uri The path or URI within that backend.
 * @returns Raw content string.
 */
export async function memoryGet(
  source: 'qmd' | 'memory',
  uri: string
): Promise<string> {
  if (source === 'qmd') {
    return await getQmd(uri);
  }
  // memory/ folder
  const filePath = path.resolve(process.cwd(), uri.startsWith('memory') ? uri : path.join('memory', uri));
  if (!fs.existsSync(filePath)) {
    throw new Error(`Memory file not found: ${filePath}`);
  }
  return fs.readFileSync(filePath, 'utf8');
}
