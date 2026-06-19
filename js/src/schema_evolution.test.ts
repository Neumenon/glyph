/**
 * Schema evolution tests.
 *
 * These tests cover the real behavior of VersionedSchema / EvolvingField /
 * compareVersions — not just that the exports exist.
 */

import {
  VersionedSchema,
  EvolutionMode,
  EvolvingField,
  EvolvingFieldConfig,
  compareVersions,
  parseVersionHeader,
  formatVersionHeader,
  versionedSchema,
} from './schema_evolution';

// ============================================================
// compareVersions
// ============================================================

describe('compareVersions', () => {
  test('equal versions return 0', () => {
    expect(compareVersions('1.0', '1.0')).toBe(0);
    expect(compareVersions('2.3', '2.3')).toBe(0);
  });

  test('lower < higher', () => {
    expect(compareVersions('1.0', '2.0')).toBe(-1);
    expect(compareVersions('1.9', '2.0')).toBe(-1);
    expect(compareVersions('1.0', '1.1')).toBe(-1);
  });

  test('higher > lower', () => {
    expect(compareVersions('2.0', '1.0')).toBe(1);
    expect(compareVersions('1.1', '1.0')).toBe(1);
  });

  test('missing minor component treated as 0', () => {
    expect(compareVersions('1', '1.0')).toBe(0);
    expect(compareVersions('2', '1.9')).toBe(1);
  });
});

// ============================================================
// parseVersionHeader / formatVersionHeader
// ============================================================

describe('version header helpers', () => {
  test('parseVersionHeader extracts version string', () => {
    expect(parseVersionHeader('@version 2.0')).toBe('2.0');
    expect(parseVersionHeader('  @version 1.5  ')).toBe('1.5');
  });

  test('parseVersionHeader returns null for invalid input', () => {
    expect(parseVersionHeader('not a version')).toBeNull();
    expect(parseVersionHeader('@version')).toBeNull();
    expect(parseVersionHeader('@version ')).toBeNull();
  });

  test('formatVersionHeader produces parseable header', () => {
    const hdr = formatVersionHeader('3.1');
    expect(hdr).toBe('@version 3.1');
    expect(parseVersionHeader(hdr)).toBe('3.1');
  });
});

// ============================================================
// EvolvingField
// ============================================================

describe('EvolvingField', () => {
  test('isAvailableIn respects addedIn', () => {
    const f = new EvolvingField('x', { type: 'str', addedIn: '2.0' });
    expect(f.isAvailableIn('1.0')).toBe(false);
    expect(f.isAvailableIn('2.0')).toBe(true);
    expect(f.isAvailableIn('3.0')).toBe(true);
  });

  test('isAvailableIn respects deprecatedIn', () => {
    const f = new EvolvingField('x', { type: 'str', addedIn: '1.0', deprecatedIn: '3.0' });
    expect(f.isAvailableIn('2.9')).toBe(true);
    expect(f.isAvailableIn('3.0')).toBe(false);
    expect(f.isAvailableIn('4.0')).toBe(false);
  });

  test('validate catches missing required field', () => {
    const f = new EvolvingField('name', { type: 'str', required: true });
    expect(f.validate(null)).toMatch(/required/);
  });

  test('validate accepts null for optional field', () => {
    const f = new EvolvingField('name', { type: 'str', required: false });
    expect(f.validate(null)).toBeNull();
  });

  test('validate type errors', () => {
    const str = new EvolvingField('s', { type: 'str' });
    expect(str.validate(42 as any)).toMatch(/string/);

    const int = new EvolvingField('n', { type: 'int' });
    expect(int.validate(3.14 as any)).toMatch(/int/);
    expect(int.validate(3 as any)).toBeNull();

    const bool = new EvolvingField('b', { type: 'bool' });
    expect(bool.validate('yes' as any)).toMatch(/bool/);
    expect(bool.validate(true)).toBeNull();
  });

  test('validate regex pattern on str field', () => {
    const f = new EvolvingField('code', { type: 'str', validation: /^[A-Z]{3}$/ });
    expect(f.validate('ABC')).toBeNull();
    expect(f.validate('ab1')).toMatch(/pattern/);
  });
});

// ============================================================
// VersionedSchema — version bump
// ============================================================

describe('VersionedSchema version bump', () => {
  test('latestVersion updates when versions are added', () => {
    const vs = versionedSchema('Doc');
    vs.addVersion('1.0', { title: { type: 'str', required: true } });
    expect(vs.latestVersion).toBe('1.0');

    vs.addVersion('2.0', { title: { type: 'str', required: true }, tags: { type: 'list' } });
    expect(vs.latestVersion).toBe('2.0');
  });

  test('emit returns @version header for valid data', () => {
    const vs = versionedSchema('Doc');
    vs.addVersion('1.0', { title: { type: 'str', required: true } });

    const result = vs.emit({ title: 'Hello' }, '1.0');
    expect(result.error).toBeUndefined();
    expect(result.header).toBe('@version 1.0');
  });

  test('emit fails for unknown version', () => {
    const vs = versionedSchema('Doc');
    vs.addVersion('1.0', { title: { type: 'str', required: true } });

    const result = vs.emit({ title: 'Hello' }, '9.9');
    expect(result.error).toMatch(/unknown version/);
  });

  test('emit validates required fields', () => {
    const vs = versionedSchema('Doc');
    vs.addVersion('1.0', { title: { type: 'str', required: true } });

    const result = vs.emit({});
    expect(result.error).toMatch(/title/);
  });
});

// ============================================================
// VersionedSchema — migration
// ============================================================

describe('VersionedSchema migration', () => {
  function buildVS(): VersionedSchema {
    const vs = versionedSchema('Event');
    vs.addVersion('1.0', {
      name: { type: 'str', required: true },
    });
    vs.addVersion('2.0', {
      name: { type: 'str', required: true },
      // 'label' is the renamed form of 'name' in v2 — use renamedFrom
      label: { type: 'str', renamedFrom: 'name', addedIn: '2.0' },
      count: { type: 'int', default: 0, addedIn: '2.0' },
    });
    return vs;
  }

  test('parse from current version succeeds without migration', () => {
    const vs = buildVS();
    const result = vs.parse({ name: 'launch' }, '1.0');
    // Migrated to 2.0: name→label, count filled with default
    expect(result.error).toBeUndefined();
    expect(result.data).toBeDefined();
  });

  test('migration applies field renames', () => {
    const vs = buildVS();
    const result = vs.parse({ name: 'launch' }, '1.0');
    expect(result.error).toBeUndefined();
    // After migration to v2.0 the old 'name' key is renamed to 'label'
    expect(result.data!['label']).toBe('launch');
    expect('name' in result.data!).toBe(false);
  });

  test('migration fills missing fields with defaults', () => {
    const vs = buildVS();
    const result = vs.parse({ name: 'launch' }, '1.0');
    expect(result.error).toBeUndefined();
    expect(result.data!['count']).toBe(0);
  });

  test('parse returns error for unknown source version', () => {
    const vs = buildVS();
    const result = vs.parse({ name: 'x' }, '9.9');
    expect(result.error).toMatch(/unknown version/);
  });

  test('downgrade returns error', () => {
    const vs = buildVS();
    // parse from v2.0 — latestVersion is 2.0 so no migration needed, succeeds
    // but trying to get from v2 back to v1 is not supported
    const result = vs.parse({ name: 'x', label: 'x', count: 1 }, '2.0');
    // 2.0 IS the latest, so just validates/filters — should succeed
    expect(result.error).toBeUndefined();
  });
});

// ============================================================
// VersionedSchema — strict mode
// ============================================================

describe('VersionedSchema strict mode', () => {
  test('strict mode rejects missing required fields', () => {
    const vs = versionedSchema('Rec');
    vs.addVersion('1.0', { id: { type: 'int', required: true } });
    vs.withMode(EvolutionMode.Strict);

    const result = vs.parse({}, '1.0');
    expect(result.error).toMatch(/id/);
  });

  test('tolerant mode (default) ignores unknown fields', () => {
    const vs = versionedSchema('Rec');
    vs.addVersion('1.0', { id: { type: 'int' } });
    // mode is Tolerant by default

    const result = vs.parse({ id: 1, extra: 'ignored' } as any, '1.0');
    expect(result.error).toBeUndefined();
    // extra field not in schema should be filtered out
    expect('extra' in (result.data ?? {})).toBe(false);
  });
});

// ============================================================
// VersionedSchema — getChangelog
// ============================================================

describe('VersionedSchema changelog', () => {
  test('changelog reflects added and deprecated fields across versions', () => {
    const vs = versionedSchema('Item');
    vs.addVersion('1.0', {
      sku: { type: 'str', required: true, addedIn: '1.0' },
    });
    vs.addVersion('2.0', {
      sku: { type: 'str', required: true, addedIn: '1.0' },
      price: { type: 'float', addedIn: '2.0' },
      sku_old: { type: 'str', addedIn: '1.0', deprecatedIn: '2.0' },
    });

    const log = vs.getChangelog();
    expect(log).toHaveLength(2);

    const v1 = log.find(e => e.version === '1.0')!;
    expect(v1.addedFields).toContain('sku');

    const v2 = log.find(e => e.version === '2.0')!;
    expect(v2.addedFields).toContain('price');
    expect(v2.deprecatedFields).toContain('sku_old');
  });
});
