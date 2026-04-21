# Pragma Logic ID Attribute Schema

This document defines the OpenTelemetry attribute names and conventions shared by
`pragma-sdk` (runtime) and `pragma` (dev-tool). Both packages MUST reference these
names from this schema, never hardcode them independently.

## Attributes

| Attribute Name | Type | Set By | Used By |
|---|---|---|---|
| `pragma.logic_id` | string | `@pragma.trace(req_id)` decorator | `pragma report` aggregator, PIL |
| `pragma.permutation` | string | `set_permutation(name)` context manager | `@trace` decorator, PIL |

## Span Name Convention

Spans emitted by `@trace` follow the pattern:

    {req_id}:{function_name}

Example: `REQ-001:register` for `@trace("REQ-001")` decorating `def register(...)`.

## Span Dump Format (JSONL)

The pytest plugin writes one JSON object per line to `.pragma/spans/test-run.jsonl`:

```json
{
  "test_nodeid": "tests/test_auth.py::test_req_001_valid",
  "span_name": "REQ-001:register",
  "attrs": {
    "pragma.logic_id": "REQ-001",
    "pragma.permutation": "valid_credentials"
  },
  "status": "ok"
}
```

Fields:
- `test_nodeid`: pytest node ID of the test that was running when the span was emitted.
- `span_name`: `{req_id}:{fn_name}` as described above.
- `attrs`: dict of span attributes (always includes `pragma.logic_id` and `pragma.permutation`).
- `status`: `"ok"` or `"error"`.

## Versioning

This schema is part of the v0.4 release. Breaking changes to attribute names require
a major version bump of both `pragma-sdk` and `pragma`.
