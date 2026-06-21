#!/usr/bin/env node
/**
 * JavaScript/TypeScript scenario runner for the GLYPH cross-language gauntlet.
 *
 * Reads the shared inputs.json, runs every scenario applicable to the JS
 * implementation, and prints a single JSON evidence object to stdout. It does
 * NOT decide pass/fail — the orchestrator is the single evaluator.
 *
 * Applicable scenarios: S1, S2, S3, S4, S5, S6 (base fingerprint only — JS has
 * no standalone verify export), S7, S8.
 * (S6 standalone accept/reject verification is Go+Py; JS base enforcement is
 * exercised through the GS1 cursor in S7.)
 *
 * Usage:  node runner.cjs <inputs.json>
 */
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const G = require(path.join(__dirname, '..', '..', 'js', 'dist', 'index.js'));
const enc = new TextEncoder();
const dec = new TextDecoder();

function cjsonBytes(value) {
  // Compact JSON byte count (per-language baseline for the savings check).
  return Buffer.byteLength(JSON.stringify(value), 'utf8');
}

function scenario(fn) {
  try {
    return { ok: true, evidence: fn() };
  } catch (e) {
    return { ok: false, error: `${e && e.name ? e.name : 'Error'}: ${e && e.message ? e.message : e}` };
  }
}

// ── S1 ──────────────────────────────────────────────────────────────────────
function s1(inp) {
  const snap = inp.S1_json_bridge.snapshot;
  const gv = G.fromJsonLoose(snap);
  const back = G.toJsonLoose(gv);
  return { roundtrip: back, equals_input: JSON.stringify(back) === JSON.stringify(snap) };
}

// ── S2 ──────────────────────────────────────────────────────────────────────
function s2(inp) {
  const d = inp.S2_canonical;
  const canons = d.variants.map((v) => G.canonicalizeLoose(G.fromJsonLoose(v)));
  const floats = {};
  for (const t of d.floats_text) floats[t] = G.canonicalizeLoose(G.parseLoose(t));
  return {
    canonical: canons[0],
    variants_consistent: canons.every((c) => c === canons[0]),
    floats,
  };
}

// ── S3 ──────────────────────────────────────────────────────────────────────
function s3(inp) {
  const d = inp.S3_fingerprint;
  return {
    fp_base: G.fingerprintLoose(G.fromJsonLoose(d.base)),
    fp_equiv: G.fingerprintLoose(G.fromJsonLoose(d.equiv)),
    fp_mutated: G.fingerprintLoose(G.fromJsonLoose(d.mutated)),
  };
}

// ── S4 ──────────────────────────────────────────────────────────────────────
function s4(inp) {
  const trace = inp.S4_tabular.trace;
  const gv = G.fromJsonLoose(trace);
  const tab = G.canonicalizeLoose(gv);
  const lst = G.canonicalizeLooseNoTabular(gv);
  const recovered = G.parseLoose(tab);
  return {
    is_tabular: tab.includes('@tab'),
    canonical_tab: tab,
    bytes_json: cjsonBytes(trace),
    bytes_list: Buffer.byteLength(lst, 'utf8'),
    bytes_tab: Buffer.byteLength(tab, 'utf8'),
    roundtrip_ok: G.equalLoose(gv, recovered),
    fp_recovered: G.fingerprintLoose(recovered),
  };
}

// ── S5 ──────────────────────────────────────────────────────────────────────
function s5(inp) {
  const d = inp.S5_patch_apply;
  const base = G.fromJsonLoose(d.base);
  const before = JSON.stringify(G.toJsonLoose(base));
  const patch = G.parsePatch(d.patch_text);
  const result = G.applyPatch(base, patch);
  return {
    result: G.toJsonLoose(result),
    fp_result: G.fingerprintLoose(result),
    base_unchanged: JSON.stringify(G.toJsonLoose(base)) === before,
  };
}

// ── S6 ──────────────────────────────────────────────────────────────────────
function s6(inp) {
  const d = inp.S6_patch_base;
  const state = G.fromJsonLoose(d.state);
  const pb = new G.PatchBuilder({ prefix: '', value: d.target })
    .withBaseValue(state)
    .set('minute', G.g.int(90))
    .build();
  return { base16: pb.baseFingerprint, verify_accept: null, verify_reject: null };
}

// ── S7 ──────────────────────────────────────────────────────────────────────
function s7(inp) {
  const d = inp.S7_gs1_stream;
  const sid = BigInt(d.sid);
  const frames = d.frames.map((f) => ({
    version: 1,
    sid,
    seq: BigInt(f.seq),
    kind: f.kind,
    payload: enc.encode(f.payload),
    final: !!f.final,
  }));
  const bytes = G.stream.encodeFrames(frames);
  const buf = Buffer.from(bytes);

  const decoded = G.stream.decodeFrames(bytes);
  const payloads_ok = decoded.length === d.frames.length &&
    decoded.every((fr, i) => dec.decode(fr.payload) === d.frames[i].payload);

  // Base-enforced cursor (fail-closed)
  const cur = new G.stream.StreamCursor();
  const st = G.fromJsonLoose(d.base_state);
  cur.setState(sid, st);
  const correct = cur.get(sid).stateHash;
  let base_accept = false;
  try {
    cur.processFrame(G.stream.patchFrame(sid, 1n, d.base_patch_payload, correct));
    base_accept = true;
  } catch (_) { base_accept = false; }
  const wrong = new Uint8Array(32); wrong[0] = 0xde;
  let base_reject = false;
  try {
    cur.processFrame(G.stream.patchFrame(sid, 2n, d.base_patch_payload, wrong));
    base_reject = false;
  } catch (_) { base_reject = true; }

  return {
    stream_sha256: crypto.createHash('sha256').update(buf).digest('hex'),
    stream_b64: buf.toString('base64'),
    frame_count: decoded.length,
    kinds: decoded.map((fr) => fr.kind),
    seqs: decoded.map((fr) => Number(fr.seq)),
    payloads_ok,
    statehash_hex: G.stream.hashToHex(G.stream.stateHashLooseSync(G.fromJsonLoose(d.base_state))),
    base_accept,
    base_reject,
  };
}

// ── S8 ──────────────────────────────────────────────────────────────────────
function feed(text) {
  const sv = new G.StreamingValidator(G.defaultToolRegistry());
  let stop = -1;
  let res = sv.getResult();
  for (const ch of text) {
    res = sv.pushToken(ch);
    if (res.errors.length > 0 && stop === -1) stop = res.charCount;
  }
  return { sv, res, stop };
}

function s8(inp) {
  const d = inp.S8_firewall;
  const a = feed(d.allowed_js);
  const allowed_accepted = a.res.complete && a.res.toolAllowed && a.res.errors.length === 0;

  const b = feed(d.blocked_js);
  const code = b.res.errors.length ? b.res.errors[0].code : '';
  const isUnknown = code === G.ErrorCode.UnknownTool;
  const total = [...d.blocked_js].length;
  return {
    allowed_accepted,
    allowed_tool: a.res.toolName,
    blocked_rejected: b.sv.shouldStop() && isUnknown,
    blocked_code: String(code),
    blocked_tool_seen: b.res.toolName,
    stop_index: b.stop,
    total_len: total,
    bytes_avoided: b.stop >= 0 ? total - b.stop : 0,
  };
}

function main() {
  const inputsPath = process.argv[2] || path.join(__dirname, 'inputs.json');
  const inp = JSON.parse(fs.readFileSync(inputsPath, 'utf8'));
  const out = {
    lang: 'js',
    version: `Node ${process.version}`,
    scenarios: {
      S1: scenario(() => s1(inp)),
      S2: scenario(() => s2(inp)),
      S3: scenario(() => s3(inp)),
      S4: scenario(() => s4(inp)),
      S5: scenario(() => s5(inp)),
      S6: scenario(() => s6(inp)),
      S7: scenario(() => s7(inp)),
      S8: scenario(() => s8(inp)),
    },
  };
  process.stdout.write(JSON.stringify(out));
}

main();
