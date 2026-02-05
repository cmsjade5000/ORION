import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';

export interface QmdResult {
  path: string;
  score: number;
  excerpt: string;
}

/**
 * Load and parse openclaw.yaml configuration from the repository root.
 */
function loadConfig(): any {
  const configPath = path.resolve(process.cwd(), 'openclaw.yaml');
  const content = fs.readFileSync(configPath, 'utf8');
  return yaml.load(content) as any;
}

/**
 * Check whether QMD backend is enabled in config.
 */
function isEnabled(config: any): boolean {
  return !!(
    config.memory &&
    config.memory.backends &&
    config.memory.backends.qmd &&
    config.memory.backends.qmd.enabled
  );
}

/**
 * Perform a search using the QMD CLI if available, otherwise fallback to simple substring search.
 * @param query The search query string.
 * @returns Array of search results with path, score, and excerpt.
 */
export async function searchQmd(query: string): Promise<QmdResult[]> {
  const config = loadConfig();
  if (!isEnabled(config)) {
    return [];
  }
  const workspace = config.memory.backends.qmd.path;
  const workspacePath = path.resolve(process.cwd(), workspace);
  if (!fs.existsSync(workspacePath) || !fs.statSync(workspacePath).isDirectory()) {
    throw new Error(`QMD workspace path does not exist: ${workspacePath}`);
  }

  let cliAvailable = true;
  try {
    execSync('qmd --version', { stdio: 'ignore' });
  } catch {
    cliAvailable = false;
  }

  if (cliAvailable) {
    // Build or refresh the index (ignore failures)
    try {
      execSync(`qmd index --quiet "${workspacePath}"`, { stdio: 'ignore' });
    } catch {
      // ignore index errors
    }
    // Query index via JSON output
    const out = execSync(`qmd query --json "${query}"`, {
      cwd: workspacePath,
      encoding: 'utf8',
    });
    const entries = JSON.parse(out) as Array<any>;
    return entries.map((e) => ({
      path: path.resolve(workspacePath, e.path),
      score: e.score,
      excerpt: e.text || e.excerpt || '',
    }));
  }

  // Fallback: simple substring search in markdown files
  const results: QmdResult[] = [];
  const files = fs.readdirSync(workspacePath).filter((f) => f.endsWith('.md'));
  for (const file of files) {
    const filePath = path.join(workspacePath, file);
    const content = fs.readFileSync(filePath, 'utf8');
    const idx = content.toLowerCase().indexOf(query.toLowerCase());
    if (idx !== -1) {
      const start = Math.max(0, idx - 40);
      const end = Math.min(content.length, idx + query.length + 40);
      const excerpt = content.substring(start, end).replace(/\s+/g, ' ');
      results.push({ path: filePath, score: 1, excerpt });
    }
  }
  return results;
}

/**
 * Retrieve the full content of a note by its relative path within the workspace.
 * @param uri The relative path (key) of the note file.
 * @returns The raw file contents.
 */
export async function getQmd(uri: string): Promise<string> {
  const config = loadConfig();
  if (!isEnabled(config)) {
    throw new Error('QMD memory backend is disabled');
  }
  const workspace = config.memory.backends.qmd.path;
  const workspacePath = path.resolve(process.cwd(), workspace);
  const filePath = path.resolve(workspacePath, uri);
  if (!fs.existsSync(filePath)) {
    throw new Error(`File not found in QMD workspace: ${uri}`);
  }
  return fs.readFileSync(filePath, 'utf8');
}
