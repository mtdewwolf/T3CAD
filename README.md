<img src="assets/icon.svg" width="64" height="64" alt="">

# T3CAD

An agent-first parametric 3D CAD workspace built on an isolated `v0.1.9` T3 Code base in [`.work/app`](.work/app).

## Capabilities

- **Parametric Feature & Command Model** ([`packages/contracts/src/cad.ts`](.work/app/packages/contracts/src/cad.ts)): Millimeter-unit documents (`CAD_SCHEMA_VERSION = 1`), stable feature IDs, multi-plane sketches (`xy`, `xz`, `yz`) for `rectangle`, `circle`, and simple `polygon` profiles (with `sketch.set_polygon_points` vertex editing), CSG `extrusion` and axisymmetric `revolve` (`u`/`v` axis, `axisOffset`, `angleDeg` in `(0, 360]`) operations (`new_body`, `union`, `cut`, `intersect`), atomic command batches, optimistic concurrency (`expectedRevision`), persisted idempotency (`requestId` + canonical digest), and revision checkpoints/rollback.
- **BSP CSG Solid Kernel & STL/OBJ Export** ([`apps/server/src/cad/CadKernel.ts`](.work/app/apps/server/src/cad/CadKernel.ts)): Evaluates multi-plane extruded and revolved feature trees (including concave polygons via ear-clipping triangulation and capped partial revolves) into watertight indexed triangle meshes, exact volume (`mm³`), surface area (`mm²`), bounding box, ASCII STL, and Wavefront OBJ output.
- **Workspace Persistence & Live Sync** ([`apps/server/src/cad/CadDocumentService.ts`](.work/app/apps/server/src/cad/CadDocumentService.ts)): Stores documents and per-revision checkpoints in `.t3cad/*.t3cad.json` inside each project workspace with keyed locking, path-containment validation, and live `PubSub` streaming over `cad.*` WebSocket RPCs (`cad.capabilities`, `cad.listDocuments`, `cad.createDocument`, `cad.inspect`, `cad.apply`, `cad.restoreRevision`, `cad.exportStl`, `cad.exportObj`, `cad.subscribeDocument`, `cad.subscribeProject`).
- **Agent MCP Harness** ([`apps/server/src/mcp/toolkits/cad/tools.ts`](.work/app/apps/server/src/mcp/toolkits/cad/tools.ts)): Exposes `cad_capabilities`, `cad_list_documents`, `cad_create_document` (`blank`, `mounting_plate`, `l_bracket`, `stepped_flange`), `cad_inspect`, `cad_apply`, `cad_restore_revision`, `cad_export_stl`, and `cad_export_obj` over `/mcp`, returning compact geometry summaries without flooding agent context with raw triangle arrays.
- **3D CAD Viewport & Inspector** ([`CadViewport3d.tsx`](.work/app/apps/web/src/components/cad/CadViewport3d.tsx), [`CadWorkspacePanel.tsx`](.work/app/apps/web/src/components/cad/CadWorkspacePanel.tsx), [`CadSketchBlueprint.tsx`](.work/app/apps/web/src/components/cad/CadSketchBlueprint.tsx)): Demand-rendered Three.js WebGL viewport (`+Z` up, `Iso`/`Top`/`Front`/`Side` presets, edge/wireframe toggles, raycast feature selection), interactive `+ Feature` builder (`Box`, `Cylinder`, `L-Polygon`, `Hole Cut`, `Revolve`), live 2D SVG sketch blueprint preview with revolve axis overlay, editable polygon vertex coordinate table, revision `Restore` provenance history, live project document auto-discovery, and STL/OBJ download. Coding-specific Pull Request, Browser Preview, and Device Simulator panes are stripped from the workbench.

## Build & Run (Isolated from Desktop State)

T3CAD's runnable application lives in [`.work/app`](.work/app) (a local gitignored checkout forked from the pinned `v0.1.9` T3 Code source, separate from `.work/upstream/t3code`). It requires Vite+ (`vp`) and Node 26 (configured in `.work/app/package.json`):

```bash
# Instantiate .work/app from pinned v0.1.9 upstream and apply T3CAD patches
python3 tools/upstream.py --setup-app

cd .work/app
vp i

# Development mode (always isolate runtime state with --home-dir)
vp run dev -- --home-dir /tmp/t3cad-home

# Production bundle build (web client + server binary)
vp run --filter @t3tools/web build
vp run --filter t3 build:bundle

# Launch production server in an isolated base directory so live T3 desktop state is untouched
node apps/server/dist/bin.mjs \
  --mode web \
  --host 127.0.0.1 \
  --port 3773 \
  --base-dir /tmp/t3cad-home \
  --auto-bootstrap-project-from-cwd /path/to/cad-workspace
```

Open the printed `pairingUrl` in a WebGL-capable browser, start a thread in the project to open the **CAD Viewport**, click **Seed Mounting Plate**, **Seed 3D L-Bracket**, or **Seed Turned Flange** (or prompt an agent via `cad_create_document`), inspect 2D sketch blueprints or add extrude/revolve features, restore any revision checkpoint, and export `.stl` or `.obj` files.

## Verification

From `.work/app`:

```bash
# Lint & typecheck
vp lint --report-unused-disable-directives
vp run -r --cache --concurrency-limit 4 typecheck

# Server & provider-core tests
vp test run \
  apps/server/src/cad/CadKernel.test.ts \
  apps/server/src/cad/CadDocumentService.test.ts \
  apps/server/src/cad/CadEdgeCases.test.ts \
  apps/server/src/mcp/toolkits/cad/CadToolkit.test.ts \
  apps/server/src/provider/AgentContextBudget.test.ts \
  apps/server/src/auth/RpcAuthorization.test.ts \
  apps/server/src/ws.test.ts \
  apps/server/src/mcp/McpHttpServer.test.ts \
  packages/provider-core/src/server/orchestrationInstructions.test.ts

# Web unit + Chromium browser tests
(cd apps/web && vp test run src/components/RightPanelTabs.test.tsx src/components/RightPanelTabs.browser.test.tsx src/lib/bootError.test.ts)
```

## Earlier Prototype & Design Notes

- [`t3cad/`](t3cad/) and [`examples/`](examples/) hold the initial headless Python proof-of-concept (`python3 -m t3cad ...`), now superseded by the TypeScript/Effect + Three.js application in [`.work/app`](.work/app).
- See [the architecture notes](docs/architecture.md) and [the source reuse audit](docs/t3code-reuse-audit.md) for initial design context.
