const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const fetch = require('node-fetch');

const CACHE_DIR = path.resolve(__dirname, '.cache/clawloan');
const TTL_MS = process.env.CLAWLOAN_CACHE_TTL_MS ? parseInt(process.env.CLAWLOAN_CACHE_TTL_MS, 10) : 3600000; // Default 1 hour
const CHECKSUM_FILE = path.resolve(__dirname, 'manifest-checksums.txt');

// Load expected checksums
const checksums = {};
if (fs.existsSync(CHECKSUM_FILE)) {
  const lines = fs.readFileSync(CHECKSUM_FILE, 'utf8').split(/\r?\n/);
  lines.forEach((line) => {
    const parts = line.split(/\s+/);
    if (parts.length >= 2) checksums[parts[1]] = parts[0];
  });
}

/**
 * Fetches a remote manifest, verifies integrity against pinned checksum, and caches it locally.
 * @param {string} url - Remote URL of the manifest
 * @param {string} filename - Local filename under cache and checksum lookup
 * @returns {Promise<string>} - The manifest content as string
 */
async function fetchManifest(url, filename) {
  await fs.promises.mkdir(CACHE_DIR, { recursive: true });
  const cachePath = path.join(CACHE_DIR, filename);
  let data;

  // Use cache if not expired
  if (fs.existsSync(cachePath)) {
    const stat = fs.statSync(cachePath);
    if (Date.now() - stat.mtimeMs < TTL_MS) {
      data = fs.readFileSync(cachePath);
    }
  }

  // Otherwise, fetch remote
  if (!data) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed to fetch ${url}: ${res.status} ${res.statusText}`);
    data = Buffer.from(await res.arrayBuffer());
    fs.writeFileSync(cachePath, data);
  }

  // Verify checksum
  const hash = crypto.createHash('sha256').update(data).digest('hex');
  const expected = checksums[filename];
  if (expected && hash !== expected) {
    throw new Error(`Checksum mismatch for ${filename}: expected ${expected} got ${hash}`);
  }

  return data.toString();
}

module.exports = { fetchManifest };
