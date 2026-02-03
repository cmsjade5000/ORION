import { provisionResources, detectDrift } from '../index';

describe('STRATUS skill stubs', () => {
  test('exports provisionResources and detectDrift functions', () => {
    expect(typeof provisionResources).toBe('function');
    expect(typeof detectDrift).toBe('function');
  });
});
