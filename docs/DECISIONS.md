# DocGuru Decisions

- The supplied master work order is the source of truth for the staged
  remediation program.
- Phase 0 adds only strict regression tests. No production behavior changes
  are included in that phase.
- Existing repository files are preserved. Commits created for this program
  stage only the files introduced by that stage.
