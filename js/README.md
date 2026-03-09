# cowrie-glyph

JavaScript / TypeScript implementation of the GLYPH codec.

## Install

```bash
npm install cowrie-glyph
```

## Quick Start

### Loose Mode

```typescript
import { fromJsonLoose, canonicalizeLoose } from 'cowrie-glyph';

const value = fromJsonLoose({
  action: 'search',
  query: 'glyph codec',
  limit: 5,
});

console.log(canonicalizeLoose(value));
// {action=search limit=5 query="glyph codec"}
```

### Schema-Oriented Encoding

```typescript
import { g, field, SchemaBuilder, t, emitPacked, parsePacked } from 'cowrie-glyph';

const schema = new SchemaBuilder()
  .addPackedStruct('Team', 'v2')
    .field('id', t.id(), { fid: 1, wireKey: 't' })
    .field('name', t.str(), { fid: 2, wireKey: 'n' })
  .build();

const team = g.struct(
  'Team',
  field('id', g.id('t', 'ARS')),
  field('name', g.str('Arsenal')),
);

const text = emitPacked(team, schema);
const parsed = parsePacked(text, schema);
```

## Main Surfaces

- loose mode: `fromJsonLoose`, `toJsonLoose`, `canonicalizeLoose`, `fingerprintLoose`
- JSON bridge: `fromJson`, `toJson`, `parseJson`
- schema: `SchemaBuilder`, `t`
- encoding: `emit`, `emitPacked`, `emitTabular`, `emitPatch`
- parsing: `parsePacked`, `parseTabular`, `parsePatch`
- streaming: `stream`, `StreamingValidator`, `ToolRegistry`

## Notes

- The npm package name is `cowrie-glyph`.
- Some older docs in this repo still say `glyph-js`; those references are historical and should not be treated as current install instructions.

For the repo-wide doc map, start at [../README.md](../README.md).
