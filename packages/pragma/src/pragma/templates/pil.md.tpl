# Pragma Verification Report — slice {{ report.slice or "all" }}

Generated: {{ report.generated_at }}
Gate: {{ report.gate or "N/A" }}
{% if report.diagnostics %}

## Diagnostics

{% for d in report.diagnostics -%}
- {{ d }}
{% endfor %}
{%- endif %}

## Summary

{{ report.summary.total }} permutations, {{ report.summary.ok }} verified, {{ report.summary.mocked + report.summary.partial + report.summary.missing + report.summary.red }} flagged.

| REQ | Title | OK | Flagged |
|---|---|---|---|
{% for req in report.requirements -%}
| {{ req.id }} | {{ req.title }} | {{ req.permutations | selectattr("status", "equalto", "ok") | list | length }} | {{ req.permutations | rejectattr("status", "equalto", "ok") | list | length }} |
{% endfor %}

{% for req in report.requirements -%}
{% for perm in req.permutations -%}
{% if perm.status.value != "ok" -%}
### {{ req.id }} / {{ perm.id }} — {{ perm.status.value }}

{{ perm.remediation or "No remediation." }}

{% endif -%}
{% endfor -%}
{% endfor -%}
