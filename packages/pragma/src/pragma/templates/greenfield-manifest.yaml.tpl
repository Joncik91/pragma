version: "2"
project:
  name: {{ project_name }}
  mode: greenfield
  language: {{ language }}
  source_root: src/
  tests_root: tests/

vision: |
  TODO(pragma): replace this paragraph with your project's vision in your
  own words. Describe what the project does, who uses it, and what the
  MVP must include.

milestones:
  - id: M01
    title: "TODO(pragma): name your first milestone"
    description: "TODO(pragma): one-paragraph description."
    depends_on: []
    slices:
      - id: M01.S1
        title: "TODO(pragma): name your first slice"
        description: "TODO(pragma): one-paragraph description."
        requirements: [REQ-000]

requirements:
  - id: REQ-000
    title: "TODO(pragma): replace with your first requirement"
    milestone: M01
    slice: M01.S1
    description: |
      TODO(pragma): describe what this requirement guarantees.
    touches:
      - src/todo.py
    permutations:
      - id: happy_path
        description: "TODO(pragma): describe the happy-path permutation."
        expected: success
