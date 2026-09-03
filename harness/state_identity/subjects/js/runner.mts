/**
 * JavaScript/TypeScript subject runner — state identity harness.
 * Same I/O contract as subjects/runner.py (see that file).
 *
 * Run from js/: npx tsx ../harness/state_identity/subjects/js/runner.mts
 * (node_modules symlink in this dir resolves `canonicalize` and tsx resolves
 *  the ../../../../js/src imports.)
 */
import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import canonicalize from "canonicalize";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import * as looseNS from "../../../../js/src/loose";
import * as parseLooseNS from "../../../../js/src/parse_loose";
import * as canonNS from "../../../../js/src/canon";
const looseMod = looseNS as unknown as Record<string, unknown> & { default?: Record<string, unknown> };
const looseImpl = (looseMod.default ?? looseMod) as unknown as {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  fromJsonLoose: (v: any) => unknown;
};
const fromJsonLoose = looseImpl.fromJsonLoose;
const canonMod = canonNS as unknown as Record<string, unknown> & { default?: Record<string, unknown> };
const canonImpl = (canonMod.default ?? canonMod) as unknown as {
  fingerprint: (v: unknown) => string;
  canonJson: (v: unknown) => string;
  isCanonical: (b: string) => boolean;
};
const fingerprintLoose = canonImpl.fingerprint;
const { canonJson, isCanonical } = canonImpl;
const parseLooseMod = parseLooseNS as unknown as Record<string, unknown> & { default?: Record<string, unknown> };
const parseLooseImpl = (parseLooseMod.default ?? parseLooseMod) as unknown as { parseLoose: (t: string) => unknown };
const parseLoose = parseLooseImpl.parseLoose;

function h(s: string | Uint8Array): string {
  return createHash("sha256").update(s).digest("hex");
}

/** Typical JS engineer's "stable stringify": recursive key sort + JSON.stringify. */
function sortKeys(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(sortKeys);
  if (v !== null && typeof v === "object") {
    const out: Record<string, unknown> = {};
    for (const k of Object.keys(v).sort()) out[k] = sortKeys((v as Record<string, unknown>)[k]);
    return out;
  }
  return v;
}

type Row = { id: string; subject: string; hash: string; error: string | null };

function runSubjects(raw: string): Row[] {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const v: any = JSON.parse(raw);
  const rows: Row[] = [];

  const naive = JSON.stringify(sortKeys(v));
  rows.push({ id: "", subject: "naive", hash: h(naive), error: null });
  rows.push({ id: "", subject: "minified", hash: h(naive), error: null }); // JSON.stringify is already compact

  try {
    const c = canonicalize(v);
    if (typeof c !== "string") throw new Error("canonicalize returned non-string");
    rows.push({ id: "", subject: "jcs", hash: h(c), error: null });
  } catch (e) {
    rows.push({ id: "", subject: "jcs", hash: "", error: `${(e as Error).name}: ${(e as Error).message}` });
  }

  try {
    rows.push({ id: "", subject: "glyph", hash: fingerprintLoose(fromJsonLoose(v)), error: null });
  } catch (e) {
    rows.push({ id: "", subject: "glyph", hash: "", error: `${(e as Error).name}: ${(e as Error).message}` });
  }
  // canon_json: the canonical bytes themselves + the idempotence check (SPEC-CANON.md §7).
  try {
    const c = canonJson(fromJsonLoose(v));
    rows.push(isCanonical(c)
      ? { id: "", subject: "canon_json", hash: h(c), error: null }
      : { id: "", subject: "canon_json", hash: "", error: "idempotence: re-canonicalization differs" });
  } catch (e) {
    rows.push({ id: "", subject: "canon_json", hash: "", error: `${(e as Error).name}: ${(e as Error).message}` });
  }
  return rows;
}

function selftest(vectorsDir: string): number {
  let total = 0;
  let failures = 0;
  for (const f of readdirSync(vectorsDir).filter((n) => n.endsWith(".input.json"))) {
    const expected = readFileSync(join(vectorsDir, f.replace(".input.json", ".expected.json")), "utf-8").trim();
    const got = canonicalize(JSON.parse(readFileSync(join(vectorsDir, f), "utf-8")));
    total++;
    if (got !== expected) {
      failures++;
      console.error(`JCS VECTOR FAIL: ${f}`);
    }
  }
  console.log(`js/canonicalize selftest: ${total - failures}/${total} vectors pass`);
  return failures ? 1 : 0;
}

function bench(payloadsPath: string): number {
  const iters = 300;
  for (const line of readFileSync(payloadsPath, "utf-8").split("\n")) {
    if (!line.trim()) continue;
    const p = JSON.parse(line) as { id: string; json: string };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const v: any = JSON.parse(p.json);
    const row: Record<string, unknown> = { id: p.id, iters };

    let t0 = performance.now();
    for (let i = 0; i < iters; i++) h(JSON.stringify(sortKeys(v)));
    row.naive_ns = Math.round((performance.now() - t0) * 1e6 / iters);

    const gv = fromJsonLoose(v);
    t0 = performance.now();
    for (let i = 0; i < iters; i++) fingerprintLoose(gv);
    row.glyph_ns = Math.round((performance.now() - t0) * 1e6 / iters);

    t0 = performance.now();
    for (let i = 0; i < iters; i++) h(canonicalize(v) as string);
    row.jcs_ns = Math.round((performance.now() - t0) * 1e6 / iters);

    process.stdout.write(JSON.stringify(row) + "\n");
  }
  return 0;
}

function main(): number {
  const argv = process.argv.slice(2);
  if (argv[0] === "--selftest") return selftest(argv[1]);

  if (argv[0] === "--mode") {
    if (argv[1] === "gtext") {
      const lines = readFileSync(0, "utf-8").split("\n");
      for (const line of lines) {
        if (!line.trim()) continue;
        const fx = JSON.parse(line) as { id: string; text: string };
        try {
          process.stdout.write(JSON.stringify({ id: fx.id, subject: "glyph", hash: fingerprintLoose(parseLoose(fx.text)), error: null }) + "\n");
        } catch (e) {
          process.stdout.write(JSON.stringify({ id: fx.id, subject: "glyph", hash: "", error: `${(e as Error).name}: ${(e as Error).message}` }) + "\n");
        }
      }
      return 0;
    }
    if (argv[1] === "bench") return bench(argv[2]);
  }

  const lines = readFileSync(0, "utf-8").split("\n");
  for (const line of lines) {
    if (!line.trim()) continue;
    const fx = JSON.parse(line) as { id: string; json: string };
    let rows: Row[];
    try {
      rows = runSubjects(fx.json);
    } catch (e) {
      const msg = `parse: ${(e as Error).name}: ${(e as Error).message}`;
      rows = ["naive", "minified", "jcs", "glyph", "canon_json"].map((s) => ({ id: fx.id, subject: s, hash: "", error: msg }));
    }
    for (const r of rows) process.stdout.write(JSON.stringify({ ...r, id: fx.id }) + "\n");
  }
  return 0;
}

process.exit(main());
