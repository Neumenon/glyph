"""Claude wrapper: ask one question, and count tokens with Claude's tokenizer.

The answer is forced through a single `submit_answer` tool so scoring is
deterministic and identical across formats (the tool schema is the same for every
format, so it adds the same constant to every prompt — fair). Token cost is
measured with `messages.count_tokens` (the real Claude tokenizer; the skill is
explicit that tiktoken is wrong for Claude), so the token figures are exact for
the model under test, not a heuristic.
"""
import anthropic

_client = None


def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN
    return _client


SYSTEM = (
    "You answer questions about a small dataset embedded in the user message. "
    "Read the data carefully. Call submit_answer with exactly the value requested "
    "— a number, a word, yes/no, or a comma-separated list of ids — and nothing else."
)

TOOL = {
    "name": "submit_answer",
    "description": "Submit the final answer to the question.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": "The answer only: a number, a word, yes/no, or "
                               "comma-separated ids. No explanation, no units.",
            }
        },
        "required": ["answer"],
        "additionalProperties": False,
    },
}


def ask(model, data_str, question, primer=""):
    """Return (answer_str_or_None, input_tokens, error_or_None)."""
    msg = f"{primer}Dataset:\n{data_str}\n\nQuestion: {question}"
    try:
        r = client().messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM,
            tools=[TOOL],
            tool_choice={"type": "tool", "name": "submit_answer"},
            messages=[{"role": "user", "content": msg}],
        )
    except Exception as exc:  # surface, don't swallow
        return None, 0, f"{type(exc).__name__}: {exc}"

    for b in r.content:
        if b.type == "tool_use" and b.name == "submit_answer":
            return str(b.input.get("answer", "")), r.usage.input_tokens, None
    return None, r.usage.input_tokens, "no submit_answer tool_use in response"


def count_tokens(model, text):
    """Token cost of an encoding, in this model's tokenizer (data only)."""
    r = client().messages.count_tokens(
        model=model, messages=[{"role": "user", "content": text}]
    )
    return r.input_tokens


# ── claude -p backend (subscription auth; no API credits) ─────────────────────
# Runs through the Claude Code CLI, which authenticates via your Claude Code login
# rather than the API credit balance. Each subprocess is an independent Claude
# instance ("sub-agent"); we batch all of a dataset's questions into one call to
# keep the count (and the per-call Claude Code wrapper overhead) low. The CC
# wrapper is cached, so usage.input_tokens reflects only OUR prompt content — the
# cross-format token delta stays valid.
import json as _json
import subprocess

_CLI_INSTR = (
    "You are given a dataset and a numbered list of questions. Answer each question "
    "by reading ONLY the data. For each, give just the value asked for — a number, a "
    "word, yes/no, or a comma-separated list of ids — with no explanation and no units. "
    'Respond with ONLY a JSON object mapping the question number (as a string) to its '
    'answer string, e.g. {"1":"42","2":"yes","3":"north"}.'
)


def _extract_json_obj(text):
    text = (text or "").strip()
    for candidate in (text, text[text.find("{"): text.rfind("}") + 1] if "{" in text else ""):
        try:
            obj = _json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def ask_cli_batch(model, data_str, questions, primer=""):
    """Answer all questions for one (dataset, format) via `claude -p`.

    Returns ({qnum_str: answer_str}, input_tokens, error_or_None).
    """
    qlines = "\n".join(f"{i + 1}. {q['text']}" for i, q in enumerate(questions))
    prompt = (f"{_CLI_INSTR}\n\n{primer}Dataset:\n{data_str}\n\n"
              f"Questions:\n{qlines}\n\nReturn ONLY the JSON object.")
    try:
        p = subprocess.run(
            ["claude", "-p", "--output-format", "json", "--model", model, "--max-turns", "1"],
            input=prompt, capture_output=True, text=True, cwd="/tmp", timeout=240,
        )
    except Exception as exc:
        return {}, 0, f"{type(exc).__name__}: {exc}"
    if p.returncode != 0:
        return {}, 0, f"cli exit {p.returncode}: {(p.stderr or p.stdout)[:200]}"
    try:
        out = _json.loads(p.stdout)
    except Exception:
        return {}, 0, f"unparseable cli stdout: {p.stdout[:200]}"
    in_tok = (out.get("usage") or {}).get("input_tokens", 0)
    answers = _extract_json_obj(out.get("result", "")) or {}
    return {str(k): str(v) for k, v in answers.items()}, in_tok, None
