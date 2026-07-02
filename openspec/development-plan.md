# Development Plan

## Future Items

### Flux 2 Editing Selected-Asset Integration

- **Status**: Planned
- **Source change**: `fix-orchestrator-selected-assets`
- **Intent**: Extend selected-asset orchestration semantics to `flux2_editing` after the current atomic-flow scope is complete.
- **Scope**: Map a selected image asset into the Flux 2 editing input contract without weakening the strict selected-asset rule.
- **Deferred because**: The current change is limited to atomic flows: `extraction`, `composition`, and `identity`.
