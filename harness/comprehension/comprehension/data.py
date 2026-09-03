"""Deterministic datasets, questions, and code-computed ground truth.

Datasets are homogeneous record lists (uniform keys → GLYPH tabular packs them).
~8 columns of mixed types stress the exact thing tabular makes hard for a reader:
mapping a positional value back to the right column for the right row.

Every question's answer is computed by *code* from the records (Rule 5 — no LLM
judge). Scoring is deterministic string/number matching, generous enough to
accept a clean value in any reasonable spelling but strict enough to fail a wrong
one — a check that can't fail when the model misreads the data is useless.
"""
import random
import re
import string

NAMES = ["Ada", "Ben", "Cara", "Dan", "Eve", "Finn", "Gia", "Hugo",
         "Ivy", "Jon", "Kai", "Lia", "Max", "Nina", "Omar", "Pia"]
REGIONS = ["north", "south", "east", "west"]
STATUS = ["pending", "shipped", "delivered", "cancelled"]


def _code(rng):
    return (rng.choice(string.ascii_uppercase) + rng.choice(string.ascii_uppercase)
            + f"{rng.randint(0, 9)}{rng.randint(0, 9)}")


def make_dataset(idx):
    rng = random.Random(1000 + idx)
    n = rng.randint(12, 18)
    base = rng.choice([100, 240, 530, 1010]) + idx * 11
    recs = []
    for i in range(n):
        recs.append({
            "id": base + i,
            "customer": rng.choice(NAMES),
            "region": rng.choice(REGIONS),
            "status": rng.choice(STATUS),
            "amount": rng.randint(10, 999),
            "items": rng.randint(1, 9),
            "priority": rng.random() < 0.4,
            "code": _code(rng),
        })
    return {"name": f"orders_{idx}", "records": recs}


def make_datasets(n):
    return [make_dataset(i) for i in range(n)]


# ── scoring helpers ───────────────────────────────────────────────────────────
def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _ints(s):
    return [int(x) for x in re.findall(r"-?\d+", str(s))]


def _fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _check_numeric(expected):
    return lambda ans: bool(_ints(ans)) and _ints(ans)[0] == expected


def _check_contains_int(expected):
    return lambda ans: expected in _ints(ans)


def _check_str(expected):
    e = _norm(expected)
    return lambda ans: _norm(ans) == e or e in [_norm(t) for t in re.split(r"[\s,]+", ans)]


def _check_bool(expected):
    def c(ans):
        a = ans.lower()
        yes = bool(re.search(r"\b(yes|true)\b", a))
        no = bool(re.search(r"\b(no|false)\b", a))
        return (yes and not no) if expected else (no and not yes)
    return c


def _check_list(ids):
    want = set(ids)
    return lambda ans: set(_ints(ans)) == want


def _q(qid, kind, text, expected, check):
    return {"qid": qid, "kind": kind, "text": text,
            "expected": expected, "expected_str": _fmt(expected) if not isinstance(expected, list)
            else ",".join(map(str, expected)), "check": check}


def make_questions(ds):
    recs = ds["records"]
    rng = random.Random(sum(ord(c) for c in ds["name"]) + 7)
    qs = []

    # Field lookups by id — forces row-then-column resolution.
    for field in ["status", "region", "amount", "customer", "code"]:
        r = rng.choice(recs)
        exp = r[field]
        if field == "amount":
            qs.append(_q(f"lookup_{field}", "lookup_num",
                         f"What is the {field} of the order with id={r['id']}?",
                         exp, _check_numeric(exp)))
        else:
            qs.append(_q(f"lookup_{field}", "lookup_str",
                         f"What is the {field} of the order with id={r['id']}?",
                         exp, _check_str(exp)))

    # Filtered counts — scan a column, count matches.
    for field in ["status", "region", "priority"]:
        val = rng.choice(recs)[field]
        exp = sum(1 for r in recs if r[field] == val)
        qs.append(_q(f"count_{field}", "count",
                     f"How many orders have {field}={_fmt(val)}?",
                     exp, _check_numeric(exp)))

    # Filtered aggregate — read two columns per row.
    region = rng.choice(REGIONS)
    exp = sum(r["amount"] for r in recs if r["region"] == region)
    qs.append(_q("sum_amount", "sum",
                 f"What is the total amount of all orders with region={region}?",
                 exp, _check_numeric(exp)))

    # Argmax — compare a column across all rows, return another column.
    mx = max(recs, key=lambda r: r["amount"])
    qs.append(_q("max_amount", "max",
                 "What is the id of the order with the highest amount?",
                 mx["id"], _check_contains_int(mx["id"])))

    # Existence — present and absent.
    present = rng.choice(recs)
    qs.append(_q("exists_yes", "exists",
                 f"Is there an order with code={present['code']}? Answer yes or no.",
                 True, _check_bool(True)))
    absent = "ZZ99"
    while any(r["code"] == absent for r in recs):
        absent = "ZZ" + str(rng.randint(10, 99))
    qs.append(_q("exists_no", "exists",
                 f"Is there an order with code={absent}? Answer yes or no.",
                 False, _check_bool(False)))

    # List ids by status — multi-row, multi-value extraction.
    statuses = [s for s in STATUS if any(r["status"] == s for r in recs)]
    val = rng.choice(statuses)
    ids = sorted(r["id"] for r in recs if r["status"] == val)
    qs.append(_q("list_status", "list",
                 f"List the ids of all orders with status={val}, comma-separated.",
                 ids, _check_list(ids)))

    return qs
