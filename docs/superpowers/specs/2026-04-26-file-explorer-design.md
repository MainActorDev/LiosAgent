# Phase 5: File Explorer — Design Spec

**Date:** 2026-04-26
**Phase:** 5 of 5 (Web UI Full Execution Dashboard)
**Branch:** develop
**Depends on:** Phases 1-4 (Foundation, Graph Dashboard, HITL Gates, Tool Call Visualization)

## Overview

Add a file explorer to the Lios Web UI that tracks all `file.read` and `file.write` events from the agent pipeline, displays them as a nested directory tree with modification badges in the sidebar, and shows unified diffs in the main content area when a file is selected.

## Architecture Decision

**Approach: Standalone `useFiles` composable** — a new `useFiles(bus)` composable in `ui/js/files.js` subscribes directly to `file.*` events on the client-side EventBus. It is independent from `useTools` (which also tracks file events for tool-call-level display). Both composables subscribe to the same bus events but serve different purposes: `useTools` tracks per-tool-call file changes, `useFiles` tracks per-file aggregate state for the explorer.

## No Backend Changes

The backend is fully ready. `ToolEventEmitter.file_read()` and `file_write()` already emit events through `EventBus` → `WSManager` → WebSocket → client. No new backend code, events, or emitters are needed.

## Data Model

### File Entry (flat map value)

```
{
  path: string,          // Full file path, e.g. "agent/tool_events.py"
  name: string,          // Basename, e.g. "tool_events.py"
  type: 'file',
  status: 'read' | 'modified' | 'new',
  reads: number,         // Count of file.read events
  writes: number,        // Count of file.write events
  lastEvent: object,     // Most recent event payload
  diffs: []              // Array of diff strings from file.write events
}
```

### Tree Node (computed from flat map)

```
{
  name: string,          // Directory or file name
  path: string,          // Full path
  type: 'dir' | 'file',
  children: [],          // Sorted: dirs first, then files, alphabetical
  expanded: boolean,     // Collapse state (dirs only, default true)
  status: string | null  // Inherited from children for dirs (new > modified > read)
}
```

### Status Priority

Directories inherit the highest-priority status from their descendants:
1. `new` (highest — green)
2. `modified` (amber)
3. `read` (muted)
4. `null` (no status)

## `useFiles(bus)` Composable

**File:** `ui/js/files.js`

**Reactive state:**
- `fileMap` — `ref({})` — flat map of `path → fileEntry`
- `tree` — `computed` — nested tree built from `fileMap`
- `selectedFile` — `ref(null)` — currently selected file path
- `selectedFileData` — `computed` — full fileEntry for the selected file

**Event handlers:**
- `file.read` → upsert into fileMap: set status to `'read'` only if not already `'modified'` or `'new'`, increment reads count, store lastEvent and preview
- `file.write` → upsert into fileMap: set status to `'new'` if `is_new_file`, otherwise `'modified'`, increment writes count, append diff to diffs array, store lastEvent

**Tree building:**
- Split each file path by `/`
- Walk segments to create/find nested directory nodes
- Directories auto-expand by default
- Sort: directories first, then files, both alphabetical
- Directory status = highest-priority child status

**Public API:**
```
{
  tree,              // Computed nested tree
  selectedFile,      // Ref to selected path
  selectedFileData,  // Computed file entry
  selectFile(path),  // Set selected file
  toggleExpand(node),// Toggle directory expand/collapse
  fileCount,         // Computed total file count
  modifiedCount      // Computed modified + new file count
}
```

## UI Layout

### Sidebar Files Accordion (existing, lines 146-175 in index.html)

Replace the current placeholder `v-for="file in files"` with a recursive tree renderer:

- **Directory nodes:** chevron icon (rotates on expand/collapse) + folder icon + name + optional status badge
- **File nodes:** file icon + name + status badge
- **Indentation:** `padding-left` increases per depth level (16px per level)
- **Click directory:** calls `toggleExpand(node)`
- **Click file:** calls `selectFile(path)`, switches main content to Files panel
- **Selected file:** highlighted with `--bg-elevated` background
- **Status badges:** small pill-shaped badges next to file/dir names
  - `M` — amber (`--accent-amber`) — modified file
  - `N` — green (`--accent-green`) — new file
  - `R` — muted (`--text-muted`) — read-only file

### Main Content Files Panel (replaces placeholder at lines 581-589)

- **Header bar:** file path as breadcrumb, status badge, read/write event counts
- **Selected file with diffs:** render each diff chronologically using `parseDiffLines()` from `useTools` and existing `.file-diff-*` CSS classes from `tools.css`
- **Selected file without diffs (read-only):** info message "File was read" with preview text if available
- **No file selected:** empty state — "Select a file from the sidebar to view details"

### Diff Rendering Reuse

The diff viewer reuses Phase 4's existing infrastructure:
- `parseDiffLines(diffString)` from `ui/js/tools.js` — parses unified diff into `{type, content}` lines
- `.file-diff-viewer`, `.file-diff-header`, `.file-diff-body`, `.file-diff-line`, `.file-diff-line.added`, `.file-diff-line.removed` from `ui/css/tools.css`

No new diff rendering code is needed.

## CSS

**File:** `ui/css/files.css`

Styles needed:
- `.file-tree` — container for the tree
- `.file-tree-node` — base node style with depth-based indentation
- `.file-tree-dir` — directory node: cursor pointer, hover highlight
- `.file-tree-file` — file node: cursor pointer, hover highlight
- `.file-tree-file.selected` — selected file: `--bg-elevated` background
- `.file-tree-chevron` — chevron icon, rotates 90deg when expanded
- `.file-badge` — base badge style (small pill)
- `.file-badge-modified` — `--accent-amber` background
- `.file-badge-new` — `--accent-green` background
- `.file-badge-read` — `--text-muted` color, subtle
- `.file-explorer-panel` — main content panel container
- `.file-explorer-header` — header with path, status, counts
- `.file-explorer-empty` — empty state styling

All styles use design tokens from `ui/css/tokens.css`.

## Wiring in `app.js`

- Import `useFiles` from `./js/files.js`
- Call `const filesExplorer = useFiles(bus)` alongside existing composable initializations
- Replace the empty `files = ref([])` with data from `filesExplorer`
- Return `filesExplorer` properties and methods to the template (`tree`, `selectedFile`, `selectedFileData`, `selectFile`, `toggleExpand`, `fileCount`, `modifiedCount`)

## File Structure

| File | Action | Description |
|------|--------|-------------|
| `ui/js/files.js` | **New** | `useFiles(bus)` composable |
| `ui/css/files.css` | **New** | File explorer styles |
| `ui/index.html` | **Edit** | Replace sidebar tree placeholder, replace main panel placeholder, add CSS link |
| `ui/js/app.js` | **Edit** | Import and wire `useFiles`, replace empty `files` ref |

## Testing Strategy

- **No new backend tests** — no backend changes
- **Existing tests remain green** — 139 tests covering event flow through bus → WS → client
- **Frontend logic is tested via manual verification** — CDN-based Vue with no build step means no JS unit test runner; the composable logic (tree building, status tracking) is verified by sending file events through the WebSocket and observing the UI
- **Integration coverage** — existing `test_tool_events.py` and `test_server.py` already verify that `file.read` and `file.write` events flow correctly from emitter through bus to WebSocket clients

## Event Flow

```
Agent pipeline
  → ToolEventEmitter.file_read() / file_write()
    → EventBus.emit("file.read" / "file.write", payload)
      → WSManager broadcasts to WebSocket clients
        → Client EventBus.dispatch(event)
          → useFiles handler: updates fileMap, tree recomputes
          → useTools handler: updates fileChanges (existing, unchanged)
```
