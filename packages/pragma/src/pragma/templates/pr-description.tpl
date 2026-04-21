## Summary

Slice {{ report.slice or "all" }} — {{ report.summary.ok }} of {{ report.summary.total }} permutations verified.

## REQs shipped

| REQ | Title | Status |
|---|---|---|
{% for req in report.requirements -%}
| {{ req.id }} | {{ req.title }} | {{ req.permutations | selectattr("status", "equalto", "ok") | list | length }}/{{ req.permutations | length }} ok |
{% endfor %}

## PIL verdict

{% for req in report.requirements -%}
### {{ req.id }}: {{ req.title }}

{% for perm in req.permutations -%}
- {{ perm.id }}: {{ perm.status.value }}
{% endfor %}
{% endfor %}

## What to review first

{% set ns = namespace(has_flagged=false) -%}
{% for req in report.requirements -%}
{% for perm in req.permutations -%}
{% if perm.status.value != "ok" -%}
{% set ns.has_flagged = true -%}
- **{{ perm.id }}** ({{ perm.status.value }}): {{ perm.remediation or "Check implementation." }}
{% endif -%}
{% endfor -%}
{% endfor -%}
{% if not ns.has_flagged -%}
All permutations verified. Review the highest-risk REQ first by touch count.
{% endif -%}
