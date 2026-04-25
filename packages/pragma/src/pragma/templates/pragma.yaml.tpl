version: "2"

project:
  name: "{{ project_name }}"
  mode: brownfield
  language: python
  source_root: src/
  tests_root: tests/

# Add requirements via:
#   pragma spec add-requirement --id REQ-001 \
#       --title "..." --description "..." \
#       --permutation 'id|description|success'
#
# Without --slice, the new REQ is assigned to M00.S0 (the implicit
# brownfield slice) so `pragma slice activate M00.S0` works without
# extra ceremony. Carve real milestones/slices when the project grows.
milestones:
- id: M00
  title: Implicit brownfield milestone
  description: Auto-created by `pragma init --brownfield`. Rename when the project grows real milestones.
  depends_on: []
  slices:
  - id: M00.S0
    title: Implicit brownfield slice
    description: Auto-created. All add-requirement entries land here until you carve real slices.
    requirements: []
requirements: []
