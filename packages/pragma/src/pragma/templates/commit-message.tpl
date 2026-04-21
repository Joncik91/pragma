{{ subject }}

WHY: {{ why }}
WHAT: Touched {{ files | length }} file(s).
WHERE: {% for f in files %}{{ f }}{% if not loop.last %}, {% endif %}{% endfor %}

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
