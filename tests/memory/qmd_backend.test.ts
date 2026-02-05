import fs from 'fs';
import os from 'os';
import path from 'path';
import { searchQmd, getQmd } from '../../src/memory/qmd_backend';

describe('QMD Backend Integration', () => {
  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'qmd-test-'));
  const workspaceDir = path.join(tmpRoot, 'workspace');
  const configPath = path.join(tmpRoot, 'openclaw.yaml');

  beforeAll(() => {
    // Create a fake workspace with a sample Markdown file
    fs.mkdirSync(workspaceDir);
    fs.writeFileSync(
      path.join(workspaceDir, 'note.md'),
      '# Test Note\n\nThis QMD test note contains the keyword foobar.'
    );
    // Write a minimal openclaw.yaml config enabling QMD backend
    const configYaml = `memory:
  backends:
    qmd:
      enabled: true
      path: ${JSON.stringify(workspaceDir)}\n`;
    fs.writeFileSync(configPath, configYaml, 'utf8');
    process.chdir(tmpRoot);
  });

  afterAll(() => {
    // Cleanup temporary directory
    process.chdir(os.tmpdir());
    fs.rmSync(tmpRoot, { recursive: true, force: true });
  });

  it('should find the sample note via fallback search when qmd CLI is not installed', async () => {
    const results = await searchQmd('foobar');
    expect(results.length).toBeGreaterThan(0);
    const match = results.find((r) => r.path.endsWith('note.md'));
    expect(match).toBeDefined();
    expect(match!.excerpt.toLowerCase()).toContain('foobar');
  });

  it('should retrieve full content of the note via getQmd', async () => {
    const content = await getQmd('note.md');
    expect(content).toContain('QMD test note');
  });
});
