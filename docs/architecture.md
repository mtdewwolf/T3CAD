# T3CAD foundation

## Status and working assumptions

This repository began as an empty project, not a fork of T3 Code. A pinned
`v0.1.9` upstream reference checkout has now been inspected; see
[the source reuse audit](t3code-reuse-audit.md). No T3 Code application code is
integrated into the runnable prototype yet, and dependency/license review is not
complete. The reference source is reproducible through `tools/upstream.py`.

The first product hypothesis is agent-assisted parametric mechanical part design.
That is a reversible starting assumption, not a commitment to cover architecture,
electronics, assemblies, or manufacturing in the first release.

The initial implementation is a headless Python prototype. It requires no runtime
dependencies and can run directly from the repository. It is not the final desktop
stack and does not require an agent-provider SDK.

## Boundaries

1. **Document:** authoritative, versioned feature definitions, explicit units,
   stable feature IDs, and command provenance. Derived geometry is not the source
   of truth.
2. **Command harness:** validated, atomic batches against an expected document
   revision. Agent identity is recorded for provenance, not treated as an
   authenticated principal. Provider adapters and UI actions should call this
   same boundary.
3. **Geometry adapter:** evaluates feature definitions without changing them.
   The bundled analytic preview adapter only measures origin-aligned rectangular
   extrusions. A real kernel must eventually generate and validate geometry.
4. **Storage:** the CLI serializes document access using a POSIX advisory lock,
   writes through a temporary file, and atomically replaces the saved document.
   Other writers must honor the same lock. This is a local file store, not a
   collaborative database or a security boundary.
5. **Application shell:** future viewport, feature tree, activity log, and review
   controls. Do not make the document depend on the chat transcript, provider,
   viewport framework, or desktop shell.

## Command semantics

Every mutation request includes `request_id`, `document_id`, `expected_revision`,
`actor`, and `commands`. A successful batch increments the revision once. A failed
command rejects the whole batch and does not alter the original document.
Unknown fields and operations are rejected instead of silently ignored.

An exact retry of a successful request returns the original receipt with
`replayed: true`, even if later revisions exist. Its reported revision is the
original commit revision; inspect the document to obtain current state. Reusing
a request ID with a different payload is rejected. Payload comparison uses
canonical JSON; `80` and `80.0` are different payloads. Failed requests are not
recorded and do not reserve an ID.

Successful requests and receipts are stored in history. Loading a document
replays that history and checks the resulting features and receipts. This detects
inconsistent edits, not malicious tampering: there are no signatures or trust
guarantees. History is append-only through the harness, not physically immutable.

All dimensions are positive millimeters, limited to 1,000,000 mm per dimension.
Rectangles lie on XY at the origin; extrusions extend along positive Z. Features
may reference only earlier features. Updating a profile changes dependent
extrusion preview measurements on the next inspection.

## Deliberate limits

- No B-rep kernel, constraint solver, actual solid geometry, renderer, or export.
- No booleans, holes, fillets, translations, assemblies, or imported geometry.
- No tool-server transport, model-provider integration, arbitrary-code tool, or
  process execution. The CLI JSON interface is the first harness surface.
- No authenticated permissions, approval workflow, sandbox, undo, or branching.
- No physical, interference, tolerance, structural, or manufacturing checks.
- History replay and snapshot receipts prioritize clarity over scalability;
  large documents will need indexed receipts, checkpoints, and migrations.
- Receipts currently include analytic preview output. Integrating a new engine
  requires separating engine-independent receipts from derived reports and
  defining engine-version compatibility before changing this format.

## Next decision gates

1. Establish an isolated build of the pinned T3 Code source, then implement the
   first CAD service/RPC/MCP slice identified in the reuse audit. The initial
   source inspection is complete; extraction, build validation, and dependency
   review remain. Do not assume shell components can be copied independently.
2. Select a geometry kernel through a spike that creates, changes, validates,
   saves, and exports one editable part. Evaluate deployment, licensing,
   persistent topology references, and headless operation.
3. Add a minimal viewport and feature inspector backed by the command boundary.
4. Expose typed agent tools over a chosen transport, with explicit capabilities
   and permissions. Add isolated execution only if script tools are introduced.
5. Add proposal/review/commit and recoverable checkpoints before autonomous
   long-running modeling sessions.

The first completed milestone is a reliable command loop with honest preview
measurements. The next milestone is a real editable solid, not a chat UI demo.
