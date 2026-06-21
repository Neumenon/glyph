'use strict';

/**
 * Glyph Gauntlet — Data Foundation Harness
 *
 * Produces gauntlet-data.json and gauntlet-data.js from the real codec.
 * Every number here comes from the actual codec output; nothing is fabricated.
 *
 * JS loose round-trip note:
 *   The JS codec is now bidirectional in loose mode:
 *     JSON value -> fromJsonLoose -> GValue -> canonicalizeLoose -> glyph text
 *     glyph text -> parseLoose -> GValue   (the inverse; parity with Go/Python)
 *   Each edge case below records its REAL round-trip status by re-parsing the
 *   emitted glyph text and checking canonical idempotence — no fake round-trip.
 */

const fs = require('fs');
const path = require('path');

const {
  canonicalizeLoose,
  canonicalizeLooseNoTabular,
  fromJsonLoose,
  parseLoose,
  parseJsonLoose,
  toJsonLoose,
  estimateTokens,
  StreamingValidator,
  ToolRegistry,
  defaultToolRegistry,
  emitPatch,
  parsePatch,
  applyPatch,
  fingerprintLoose,
  g,
  field,
  PatchBuilder,
} = require('../../js/dist/index.js');

// ============================================================
// Utilities
// ============================================================

function byteLen(s) {
  return Buffer.byteLength(s, 'utf8');
}

function savingsPct(baseBytes, newBytes) {
  if (baseBytes === 0) return 0;
  return parseFloat(((1 - newBytes / baseBytes) * 100).toFixed(2));
}

function makeMatchRow(i) {
  return {
    id: `m${i}`,
    home: `Team_${(i % 20) + 1}`,
    away: `Team_${((i + 10) % 20) + 1}`,
    score_home: i % 5,
    score_away: (i + 1) % 4,
    minute: (i * 3) % 90,
    status: i % 3 === 0 ? 'live' : (i % 3 === 1 ? 'finished' : 'upcoming'),
    venue: `Stadium_${(i % 8) + 1}`,
  };
}

// ============================================================
// SECTION: meta
// ============================================================

const meta = {
  generatedNote: 'All numbers from real codec execution. No values fabricated.',
  glyphPackage: 'cowrie-glyph',
  node: process.version,
  tokenizer: 'heuristic estimateTokens (whitespace split — NOT a real BPE tokenizer; token savings figures are illustrative only)',
};

// ============================================================
// SECTION: edgeCases
// ============================================================

function measureEdgeCase(name, jsValue, note) {
  let jsonText, glyphText;
  let roundTrip = 'ok';
  let roundTripNote;
  try {
    jsonText = JSON.stringify(jsValue);
  } catch (e) {
    jsonText = `<error: ${e.message}>`;
  }
  try {
    const gv = fromJsonLoose(jsValue);
    glyphText = canonicalizeLoose(gv);
  } catch (e) {
    glyphText = `<error: ${e.message}>`;
  }
  // Real round-trip: parseLoose now inverts canonicalizeLoose in JS (parity with
  // Go ParseDocument / Python parse). The invariant is canonical idempotence —
  // re-emitting the parsed value must reproduce the exact same glyph text.
  try {
    const reparsed = parseLoose(glyphText);
    const reText = canonicalizeLoose(reparsed);
    if (reText === glyphText) {
      roundTrip = 'ok';
      roundTripNote = 'JS round-trips: canonicalizeLoose <-> parseLoose is a fixed point.';
    } else {
      roundTrip = 'lossy';
      roundTripNote = `parseLoose re-emit differs: ${reText}`;
    }
  } catch (e) {
    roundTrip = 'unsupported';
    roundTripNote = `parseLoose error: ${e.message}`;
  }
  return { name, jsonText, glyphText, note, roundTrip, roundTripNote };
}

const edgeCases = [
  measureEdgeCase('empty_str', '', 'Empty string — needs quotes in glyph'),
  measureEdgeCase('unicode', 'café ☕ λ', 'Unicode: café ☕ λ'),
  measureEdgeCase('embedded_quote', 'say "hello"', 'Embedded double-quotes'),
  measureEdgeCase('pipe', 'a|b|c', 'Pipe chars — must be escaped in tabular cells'),
  measureEdgeCase('newlines', 'line1\nline2\r\nline3', 'Embedded newlines'),
  measureEdgeCase('null_value', null, 'JSON null -> glyph _'),
  measureEdgeCase('bool_true', true, 'bool true -> t'),
  measureEdgeCase('bool_false', false, 'bool false -> f'),
  // 9007199254740993 is Number.MAX_SAFE_INTEGER + 1 — precision loss in JS
  measureEdgeCase('big_int', 9007199254740993, 'Exceeds Number.MAX_SAFE_INTEGER — JS loses precision here; Go/Py handle correctly with int64'),
  measureEdgeCase('float_sci', 1.23e-9, 'Small float scientific notation'),
  measureEdgeCase('neg_zero', -0, 'Negative zero -> 0.0 in glyph'),
  measureEdgeCase('date_string', '2024-03-15T12:00:00Z', 'ISO date string — stays as string in loose mode (no type inference)'),
  measureEdgeCase('nested_list', [1, 2, 'three', null], 'Mixed-type list'),
  measureEdgeCase('nested_map', { a: 1, b: { c: 2 } }, 'Nested map'),
];

// ============================================================
// SECTION: toolFirewall
// ============================================================

function measureFirewall() {
  // defaultToolRegistry has: search, calculate, browse, execute, read_file, write_file
  // wire_transfer is NOT in that registry — rejection is native
  const registry = defaultToolRegistry();

  const allowedText = '{action=search query="latest weather in Chicago" max_results=5}';
  const blockedText = '{action=wire_transfer amount=1000000 target=unknown}';

  // --- allowed stream ---
  const allowedSV = new StreamingValidator(registry);
  let allowedResult;
  for (const c of allowedText) {
    allowedResult = allowedSV.pushToken(c);
  }

  // --- blocked stream ---
  const blockedSV = new StreamingValidator(registry);
  let blockedResult;
  let rejectChar = null;
  for (const c of blockedText) {
    blockedResult = blockedSV.pushToken(c);
    if (rejectChar === null && blockedSV.shouldStop()) {
      rejectChar = blockedResult.charCount;
    }
  }

  const totalBlockedChars = byteLen(blockedText); // chars == bytes for ASCII
  const bytesAvoided = rejectChar !== null ? totalBlockedChars - rejectChar : 0;

  return {
    registryNote: 'defaultToolRegistry includes: search, calculate, browse, execute, read_file, write_file. wire_transfer is absent — rejection is native to the default registry; no custom allowlist was needed.',
    allowed: {
      text: allowedText,
      totalChars: allowedText.length,
      toolName: allowedResult.toolName,
      toolDetectedAtChar: allowedResult.toolDetectedAtChar,
      allowed: allowedResult.toolAllowed,
      errors: allowedResult.errors,
      timeline: allowedResult.timeline,
    },
    blocked: {
      text: blockedText,
      totalChars: blockedText.length,
      toolName: blockedResult.toolName,
      toolDetectedAtChar: blockedResult.toolDetectedAtChar,
      allowed: blockedResult.toolAllowed,
      rejectAtChar: rejectChar,
      bytesAvoided,
      errors: blockedResult.errors,
      timeline: blockedResult.timeline,
    },
  };
}

const toolFirewall = measureFirewall();

// ============================================================
// SECTION: matchStream
// ============================================================

function measureMatchStream() {
  // Base match snapshot
  const baseSnap = {
    id: 'match_001',
    home: 'Arsenal',
    away: 'Chelsea',
    score_home: 0,
    score_away: 0,
    minute: 0,
    status: 'live',
    events: [],
  };

  // We use emitPatch from the real codec.
  // PatchBuilder requires a RefID target.
  // The JS PatchBuilder takes a RefID: {prefix, value}
  const matchRef = { prefix: 'match', value: '001' };

  const perUpdate = [];
  let cumSnapshotBytes = 0;
  let cumPatchBytes = 0;

  let currentSnap = JSON.parse(JSON.stringify(baseSnap));

  const N_UPDATES = 100;
  for (let i = 0; i < N_UPDATES; i++) {
    // Simulate a live match update
    const newMinute = i + 1;
    const newScoreHome = Math.floor(i / 20);
    const newScoreAway = Math.floor(i / 25);

    // Build snapshot
    currentSnap = {
      ...currentSnap,
      minute: newMinute,
      score_home: newScoreHome,
      score_away: newScoreAway,
    };
    const snapJSON = JSON.stringify(currentSnap);
    const snapBytes = byteLen(snapJSON);
    cumSnapshotBytes += snapBytes;

    // Build a real glyph patch using PatchBuilder
    let patchText, patchBytes;
    try {
      const builder = new PatchBuilder(matchRef);
      builder.set('minute', g.int(newMinute));
      builder.set('score_home', g.int(newScoreHome));
      builder.set('score_away', g.int(newScoreAway));
      const patch = builder.build();
      patchText = emitPatch(patch);
      patchBytes = byteLen(patchText);
    } catch (e) {
      patchText = `<error: ${e.message}>`;
      patchBytes = 0;
    }
    cumPatchBytes += patchBytes;

    perUpdate.push({
      update: i + 1,
      minute: newMinute,
      snapshotBytes: snapBytes,
      patchBytes,
    });
  }

  // Sample patch text for documentation
  let samplePatchText = '';
  try {
    const builder = new PatchBuilder(matchRef);
    builder.set('minute', g.int(45));
    builder.set('score_home', g.int(1));
    builder.set('score_away', g.int(0));
    const patch = builder.build();
    samplePatchText = emitPatch(patch);
  } catch (e) {
    samplePatchText = `<error: ${e.message}>`;
  }

  const savingsPctVal = savingsPct(cumSnapshotBytes, cumPatchBytes);

  return {
    measurementNote: 'Patch bytes measured using real emitPatch(PatchBuilder.build()). Each update patches 3 fields: minute, score_home, score_away. snapshotBytes = JSON.stringify(full snapshot). patchBytes = real @patch text bytes.',
    samplePatchText,
    totalUpdates: N_UPDATES,
    cumSnapshotBytes,
    cumPatchBytes,
    savingsPct: savingsPctVal,
    perUpdate,
  };
}

const matchStream = measureMatchStream();

// ============================================================
// SECTION: tabular
// ============================================================

function measureTabular(rowCounts) {
  return rowCounts.map(rows => {
    const data = [];
    for (let i = 0; i < rows; i++) {
      data.push(makeMatchRow(i));
    }

    const jsonMin = JSON.stringify(data);
    const jsonPretty = JSON.stringify(data, null, 2);

    // glyph loose — canonicalizeLoose auto-tabularizes for homogeneous arrays
    const gv = fromJsonLoose(data);
    const glyphLoose = canonicalizeLoose(gv);

    // Note: canonicalizeLoose already auto-tabularizes.
    // There is no separate emitTabular path for loose mode —
    // the same function handles it via defaultLooseCanonOpts().autoTabular=true.
    const glyphTabularNote = 'canonicalizeLoose auto-tabularizes; no separate loose emitTabular path exists.';

    const jsonMinBytes = byteLen(jsonMin);
    const jsonPrettyBytes = byteLen(jsonPretty);
    const glyphLooseBytes = byteLen(glyphLoose);

    const tokensJsonMin = estimateTokens(jsonMin);
    const tokensGlyphLoose = estimateTokens(glyphLoose);

    return {
      rows,
      jsonMinBytes,
      jsonPrettyBytes,
      glyphLooseBytes,
      glyphTabularNote,
      tokens: {
        jsonMin: tokensJsonMin,
        glyphLoose: tokensGlyphLoose,
        tokenizerWarning: 'heuristic whitespace split — not a real BPE tokenizer',
      },
      savingsBytesPct: savingsPct(jsonMinBytes, glyphLooseBytes),
      savingsTokensPct: savingsPct(tokensJsonMin, tokensGlyphLoose),
      // First 200 chars of glyph output for inspection
      glyphLoosePreview: glyphLoose.slice(0, 200) + (glyphLoose.length > 200 ? '...' : ''),
    };
  });
}

const tabular = measureTabular([10, 100, 1000, 10000]);

// ============================================================
// SECTION: benchMatrix
// ============================================================

function buildDatasets() {
  // tinyToolCalls: array of ~100 tool-call objects
  const tinyToolCalls = [];
  for (let i = 0; i < 100; i++) {
    tinyToolCalls.push({
      tool: i % 3 === 0 ? 'search' : (i % 3 === 1 ? 'calculate' : 'browse'),
      args: {
        query: `query number ${i}`,
        max_results: (i % 10) + 1,
      },
      call_id: `tc_${i}`,
    });
  }

  // nestedAgentTrace: one deeply nested object (10 levels)
  function makeNested(depth) {
    if (depth === 0) return { value: 42, leaf: true };
    return { level: depth, child: makeNested(depth - 1), metadata: `level_${depth}` };
  }
  const nestedAgentTrace = {
    trace_id: 'agent_trace_001',
    steps: 10,
    root: makeNested(10),
    summary: 'deep nested agent execution trace',
  };

  // repeatedRows: 1000 homogeneous match rows
  const repeatedRows = [];
  for (let i = 0; i < 1000; i++) {
    repeatedRows.push(makeMatchRow(i));
  }

  // adversarialStrings: values with edge-case characters
  const adversarialStrings = [
    '',
    '"quoted"',
    'back\\slash',
    'a|b|c',
    'éλ☕\u{1F600}',
    true,
    false,
    null,
    9007199254740993,
    'SGVsbG8gV29ybGQ=', // base64-looking
    '{"key": "value"}', // JSON-looking string
    '42',               // number-looking string
    '-0',
    'true',             // bool-looking string
    'null',             // null-looking string
  ];

  return { tinyToolCalls, nestedAgentTrace, repeatedRows, adversarialStrings };
}

function measureDataset(name, data) {
  const jsonMin = JSON.stringify(data);
  const jsonPretty = JSON.stringify(data, null, 2);

  let glyphLoose, glyphLooseBytes, tokensGlyph;
  try {
    const gv = fromJsonLoose(data);
    glyphLoose = canonicalizeLoose(gv);
    glyphLooseBytes = byteLen(glyphLoose);
    tokensGlyph = estimateTokens(glyphLoose);
  } catch (e) {
    glyphLoose = `<error: ${e.message}>`;
    glyphLooseBytes = 0;
    tokensGlyph = 0;
  }

  const jsonMinBytes = byteLen(jsonMin);
  const jsonPrettyBytes = byteLen(jsonPretty);
  const tokensJsonMin = estimateTokens(jsonMin);
  const tokensJsonPretty = estimateTokens(jsonPretty);

  return {
    dataset: name,
    formats: {
      jsonMin: { bytes: jsonMinBytes, tokens: tokensJsonMin },
      jsonPretty: { bytes: jsonPrettyBytes, tokens: tokensJsonPretty },
      glyphLoose: { bytes: glyphLooseBytes, tokens: tokensGlyph },
    },
    savingsVsJsonMin: {
      bytesPct: savingsPct(jsonMinBytes, glyphLooseBytes),
      tokensPct: savingsPct(tokensJsonMin, tokensGlyph),
    },
    availableFormatsNote: 'Only jsonMin, jsonPretty, glyphLoose measured. schemaful formats (packed, tabular-schemaful) omitted — they require a Schema definition not relevant to loose mode.',
    tokenizerWarning: 'heuristic whitespace split — not a real BPE tokenizer',
  };
}

const { tinyToolCalls, nestedAgentTrace, repeatedRows, adversarialStrings } = buildDatasets();

const benchMatrix = [
  measureDataset('tinyToolCalls', tinyToolCalls),
  measureDataset('nestedAgentTrace', nestedAgentTrace),
  measureDataset('repeatedRows', repeatedRows),
  measureDataset('adversarialStrings', adversarialStrings),
];

// ============================================================
// SECTION: schemaHashNote
// ============================================================

const schemaHashNote =
  'Loose canonical mode is entirely schema-free. Field IDs (FIDs) and schema hashes are Go/schema concerns: ' +
  'in Go, structured types can carry FIDs (compact numeric field aliases) that appear in packed/tabular schemaful ' +
  'formats. In loose mode (canonicalizeLoose), all keys are emitted as plain strings — there are no FID substitutions, ' +
  'no @schema header, and no schema hash in the output. The FID/schema-hash trap (verifying that a decoded value ' +
  'actually matches its declared schema version) is exercised by the Go test suite against schemaful formats only.';

// ============================================================
// Assemble + Write
// ============================================================

const gauntletData = {
  meta,
  edgeCases,
  toolFirewall,
  matchStream,
  tabular,
  benchMatrix,
  schemaHashNote,
};

const dataDir = path.join(__dirname, '..', 'data');
const jsonPath = path.join(dataDir, 'gauntlet-data.json');
const jsPath = path.join(dataDir, 'gauntlet-data.js');

const jsonText = JSON.stringify(gauntletData, null, 2);
fs.writeFileSync(jsonPath, jsonText, 'utf8');
fs.writeFileSync(jsPath, `window.GAUNTLET_DATA = ${jsonText};\n`, 'utf8');

console.log('Written:', jsonPath);
console.log('Written:', jsPath);

// ============================================================
// Headline numbers
// ============================================================
console.log('\n=== HEADLINE NUMBERS ===');
const tab100 = tabular.find(t => t.rows === 100);
console.log(`Tabular savings (100 rows, bytes): ${tab100.savingsBytesPct}%  (jsonMin=${tab100.jsonMinBytes}B -> glyph=${tab100.glyphLooseBytes}B)`);
const tab50 = tabular.find(t => t.rows === 10); // closest to documented 50-row example
console.log(`Tabular savings (10 rows, bytes):  ${tab50.savingsBytesPct}%  (jsonMin=${tab50.jsonMinBytes}B -> glyph=${tab50.glyphLooseBytes}B)`);
console.log(`Patch savings vs snapshot (${matchStream.totalUpdates} updates): ${matchStream.savingsPct}%`);
console.log(`Firewall: wire_transfer rejected at char ${toolFirewall.blocked.rejectAtChar} / ${toolFirewall.blocked.totalChars}, bytesAvoided=${toolFirewall.blocked.bytesAvoided}`);
const benchRepeated = benchMatrix.find(b => b.dataset === 'repeatedRows');
console.log(`BenchMatrix repeatedRows (1000 rows): jsonMin=${benchRepeated.formats.jsonMin.bytes}B -> glyph=${benchRepeated.formats.glyphLoose.bytes}B (${benchRepeated.savingsVsJsonMin.bytesPct}% savings)`);
const benchTool = benchMatrix.find(b => b.dataset === 'tinyToolCalls');
console.log(`BenchMatrix tinyToolCalls (100 items): jsonMin=${benchTool.formats.jsonMin.bytes}B -> glyph=${benchTool.formats.glyphLoose.bytes}B (${benchTool.savingsVsJsonMin.bytesPct}% savings)`);
