# T3 Code reuse audit

## Audited baseline

- Repository: `https://github.com/pingdotgg/t3code.git`.
- Release tag: `v0.1.9`.
- Commit: `24e77473ecf41bc1f7142529c7911c1c1aae1d76`.
- Audit date: November 15, 2026.
- Reason: the local desktop launcher names `T3-Code-0.1.9-x86_64.AppImage`.
  This matches a version label, not a verified binary/source correspondence,
  and is not a selection of the latest available release.
- Local source: `.work/upstream/t3code`, ignored by this repository.

The root LICENSE identifies MIT. Its exact fingerprint is in
`upstream/t3code.lock.json`. Dependencies and bundled assets have their own
notices; the root file is not a complete dependency-license review. Before
redistributing adapted code, retain its required notices and audit the shipped
dependency closure. Upstream's notice-generation approach is documented in
`docs/internals/open-source-licenses.md`.

Reproduce or check the source with:

```bash
python3 tools/upstream.py --fetch
python3 tools/upstream.py
```

The helper checks the origin, commit, tag, worktree, and root notice fingerprint.
It never resets a checkout, installs dependencies, runs upstream code, or accesses
the live T3 database. This is a revision pin, not cryptographic publisher-signature
verification.

## What the source actually contains

The upstream is an Electron desktop shell around a React web client, with a Node
server that owns workspace files, provider processes, and orchestration. Effect
schemas and RPC form a shared client/server boundary. Provider adapters normalize
agent runtimes; MCP tools call server-owned services with caller/access checks.

The key evidence, relative to the reference checkout:

| Area | Source to inspect | CAD disposition |
| --- | --- | --- |
| Ownership and execution boundaries | `docs/internals/overview.md` | Retain the server-owned execution model |
| Desktop boot and platform services | `apps/desktop/src/main.ts`, `apps/desktop/src/app`, `apps/desktop/src/backend` | Retain initially, then reduce |
| Shared schemas and RPC | `packages/contracts/src/rpc.ts` | Extend with a separate CAD namespace |
| Provider normalization | `packages/provider-core/src/server/ProviderAdapter.ts`, `apps/server/src/provider` | Retain one supported runtime first |
| Durable agent runs | `apps/server/src/orchestration-v2/Orchestrator.ts`, `EventSink.ts`, `EffectWorker.ts` | Retain agent-run orchestration; do not make it CAD history |
| Agent tool surface | `apps/server/src/mcp/McpHttpServer.ts`, `toolkits/html/tools.ts`, `toolkits/html/handlers.ts` | Follow the schema/service/handler pattern for CAD tools |
| Tool authorization | `apps/server/src/mcp/McpInvocationContext.ts`, `McpToolAccess.ts`, `threadAccess.ts` | Extend with document-level authorization |
| Web layout | `apps/web/src/routes/_chat.tsx`, `apps/web/src/components` | Replace chat-first composition with CAD workspace |
| Shared client state | `packages/client-runtime/package.json`, `packages/client-runtime/src` | Extract selectively, not as a supposedly independent drop-in |
| Notice generation | `docs/internals/open-source-licenses.md` | Keep a release notice pipeline |

The root manifest pins Node `26.12.1` and `pnpm@12.14.0`; development uses Vite+.
Neither Node nor the package manager is currently installed on PATH here. The
source was inspected but not installed, built, or launched.

## Important coupling and non-equivalences

1. `packages/client-runtime` directly depends on numerous provider and
   source-control packages. Copying it plus the desktop shell will not produce a
   minimal CAD application. The server manifest also directly includes multiple
   providers and source-control integrations.
2. Agent-run history is not durable CAD feature history. Upstream's overview
   explicitly describes event-log pruning and persisted projections. Do not use
   that reconnect stream as the sole record needed to rebuild a model.
3. A committed orchestration command records intent; a subsequent effect can
   still fail. A CAD edit must have its own transaction and evaluation outcome.
   Distinguish a queued modeling job from a successfully committed model revision.
4. Provider approval policies are not a CAD document permission system. A tool
   must validate the calling environment, project, document, and action scope.
5. Existing 3D-related dependencies or preview facilities are not evidence of a
   CAD kernel, sketch solver, stable topology naming, or manufacturing validation.
6. The Python prototype is an experiment, not a second permanent document owner.
   Decide whether the authoritative service is a TypeScript port or a supervised
   worker before connecting it to persistent T3 state.

## Proposed reduction strategy

Use a staged reduction of a pinned upstream base, not a bulk copy of a handful of
UI files. First establish an isolated upstream build; then add one CAD vertical
slice; only remove features after the slice works and dependency paths are known.
The reference checkout stays pristine until a deliberate working source layout
is chosen. It is not currently the product checkout.

### Retain initially

- Desktop window lifecycle, theme/platform integration, and local server boot.
- Environment-owned RPC/authentication and typed contracts.
- Project/thread identity, one provider runtime, and visible run/tool activity.
- Existing permissions as an outer boundary, with CAD-specific checks inside it.

### Hide first, remove after dependency checks

- Git diffs, worktree workflows, pull requests, review guides, and source-control
  integrations. Version control can be revisited for design artifacts later.
- Browser automation, device emulators, voice, scheduling, and auxiliary tools.
- Remote tunnels, mobile clients, hosted services, and multiple provider setups
  from the first product surface. Preserve required local authentication; do not
  turn off access checks simply because the UI starts local-only.

### Build specifically for CAD

- A separate versioned CAD document store and command service.
- Geometry evaluation worker with timeout, cancellation, and typed failures.
- Feature tree, parameter inspector, selection model, and viewport.
- CAD measurements and validation tools with explicit kernel/version metadata.
- Proposal, review, commit, checkpoint, and recovery semantics for agent edits.

## First integration change set

The following paths are proposed additions to a future working upstream base,
not files already implemented by this audit:

1. **Contracts:** `packages/contracts/src/cad.ts` defines document summaries,
   feature IDs, revisioned command batches, operation receipts, and typed errors.
   Register `cad.inspect`, `cad.apply`, and a revision subscription in `rpc.ts`.
2. **Server:** `apps/server/src/cad/CadDocumentService.ts` owns file resolution,
   authorization, document transactions, and geometry-adapter access. Resolve
   documents inside the owning project; do not accept arbitrary agent-supplied
   filesystem paths. Route both UI RPC and MCP handlers through this service.
3. **Agent tools:** add `apps/server/src/mcp/toolkits/cad/tools.ts` and
   `handlers.ts`, register them with `McpHttpServer.ts`, and explicitly apply the
   existing caller/access checks plus document scope. Use `cad_inspect` and
   `cad_apply` as the first tools; do not add arbitrary Python/shell execution.
4. **Client:** introduce a CAD workspace route that shows document state and
   agent activity. Use the same command service for a parameter edit and an agent
   edit; never let the renderer write a document directly.
5. **Lifecycle:** if Python remains a worker, use a versioned request protocol,
   fixed executable/arguments, a supervisor, bounded payloads/output, explicit
   timeouts, cancellation, and clean shutdown. The JSON CLI alone is not that
   production worker protocol. Do not share a writable store between competing
   TypeScript and Python owners.

Acceptance gate: a manual parameter edit and an agent edit produce equivalent
feature state; dependent measurements update; stale revisions fail; retries do
not duplicate edits; an invalid geometry result leaves the committed model
unchanged; restarting the application preserves the document and activity.
An analytic-only implementation must remain labeled as a preview, not a solid.

## Current integration status

Actual T3 application code used by the runnable T3CAD prototype: **none**.
Actual progress in this audit: upstream source is available locally, pinned and
verifiable, and the concrete integration seams have been inspected. No live T3
settings, database, installed binary, or provider configuration was modified.
