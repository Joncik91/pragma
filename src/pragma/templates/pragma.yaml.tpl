version: "1"

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
requirements: []
