# File Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a file explorer to the Lios Web UI that tracks `file.read` and `file.write` events, displays a nested directory tree with modification badges in the sidebar, and shows unified diffs in the main content area when a file is selected.

**Architecture:** A standalone `useFiles(bus)` composable subscribes to `file.*` events on the client-side EventBus, builds a reactive file tree from a flat map, and provides selection/expand/collapse state. The sidebar renders the tree recursively with status badges (M/N/R). The main content panel shows diffs using the existing `parseDiffLines()` from `useTools` and `.file-diff-*` CSS from Phase 4. No backend changes needed — `file.read` and `file.write` events already flow through `EventBus` → `WSManager` → WebSocket → client.

**Tech Stack:** Vue 3 CDN (composable + HTML template), vanilla CSS with design tokens, no build step

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `ui/js/files.js` | **Create** | `useFiles(bus)` composable — reactive file tree from `file.*` events |
| `ui/css/files.css` | **Create** | File explorer tree styles, badges, main panel layout |
| `ui/js/app.js` | **Modify** | Import and wire `useFiles`, replace empty `files` ref |
| `ui/index.html` | **Modify** | Replace sidebar tree placeholder, replace main panel placeholder, add CSS link |

---

## Task Summary

| Task | Component | Description |
|------|-----------|-------------|
| 1 | `ui/js/files.js` | `useFiles(bus)` composable — file map, tree building, selection |
| 2 | `ui/css/files.css` | File explorer styles — tree nodes, badges, main panel |
| 3 | `ui/js/app.js` | Wire `useFiles` into the Vue app |
| 4 | `ui/index.html` — sidebar | Replace sidebar Files accordion with recursive tree |
| 5 | `ui/index.html` — main panel | Replace Files placeholder with diff viewer panel |
| 6 | Integration verification | End-to-end manual test + existing test suite |

---

### Task 1: `useFiles(bus)` Composable

**Files:**
- Create: `ui/js/files.js`

This composable follows the exact pattern of `useGates(bus, sendCommand)` in `ui/js/gates.js`. It subscribes to `file.read` and `file.write` events, maintains a flat `fileMap` of path → entry, and computes a nested tree.

- [ ] **Step 1: Create `ui/js/files.js` with the full composable**

Create `ui/js/files.js`:

```javascript
/**
 * useFiles composable — tracks file read/write events and builds a reactive tree.
 *
 * Subscribes to file.read and file.write events on the client-side EventBus.
 * Independent from useTools (which tracks per-tool-call file changes).
 * This composable tracks per-file aggregate state for the explorer.
 *
 * @param {EventBus} bus - Client-side event bus
 * @returns {Object} Reactive file tree state and actions
 */
export function useFiles(bus) {
  const { ref, computed } = Vue;

  // ── Reactive State ──────────────────────────────────────────────

  /** @type {import('vue').Ref<Object>} Flat map of path → file entry */
  const fileMap = ref({});

  /** @type {import('vue').Ref<string|null>} Currently selected file path */
  const selectedFile = ref(null);

  // ── Computed ────────────────────────────────────────────────────

  /** Total number of tracked files */
  const fileCount = computed(() => Object.keys(fileMap.value).length);

  /** Number of modified or new files */
  const modifiedCount = computed(() =>
    Object.values(fileMap.value).filter(
      (f) => f.status === 'modified' || f.status === 'new'
    ).length
  );

  /** Full file entry for the selected file */
  const selectedFileData = computed(() => {
    if (!selectedFile.value) return null;
    return fileMap.value[selectedFile.value] || null;
  });

  /** Nested tree computed from flat fileMap */
  const tree = computed(() => buildTree(fileMap.value));

  /** Flattened tree for template rendering (with depth info) */
  const flatTree = computed(() => {
    const result = [];
    function walk(nodes, depth) {
      if (!nodes) return;
      for (const node of nodes) {
        result.push({ ...node, depth, children: undefined });
        if (node.type === 'dir' && isExpanded(node.path) && node.children) {
          walk(node.children, depth + 1);
        }
      }
    }
    if (tree.value && tree.value.children) {
      walk(tree.value.children, 0);
    }
    return result;
  });

  // ── Tree Building ───────────────────────────────────────────────

  /**
   * Build a nested tree from the flat fileMap.
   * Each file path is split by '/' to create directory nodes.
   * Directories auto-expand by default.
   * Sort: directories first, then files, both alphabetical.
   * Directory status = highest-priority child status.
   */
  function buildTree(map) {
    const root = { children: {} };

    for (const [filePath, entry] of Object.entries(map)) {
      const parts = filePath.split('/');
      let current = root;

      for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        const isFile = i === parts.length - 1;

        if (!current.children[part]) {
          current.children[part] = isFile
            ? {
                name: part,
                path: filePath,
                type: 'file',
                status: entry.status,
                children: null,
              }
            : {
                name: part,
                path: parts.slice(0, i + 1).join('/'),
                type: 'dir',
                expanded: true,
                children: {},
              };
        }

        if (isFile) {
          // Update status on existing node
          current.children[part].status = entry.status;
        } else {
          current = current.children[part];
        }
      }
    }

    return sortTree(objectToArray(root));
  }

  /**
   * Convert the object-based tree to arrays of children.
   * Returns the root's children as an array.
   */
  function objectToArray(node) {
    if (!node.children || typeof node.children !== 'object') return node;

    const result = { ...node };
    result.children = Object.values(node.children).map((child) => {
      if (child.type === 'dir') {
        const converted = objectToArray(child);
        converted.status = computeDirStatus(converted.children);
        return converted;
      }
      return { ...child };
    });
    return result;
  }

  /**
   * Sort tree nodes: directories first, then files, both alphabetical.
   * Recurse into directory children.
   */
  function sortTree(node) {
    if (!node.children || !Array.isArray(node.children)) return node;

    node.children.sort((a, b) => {
      if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });

    node.children.forEach((child) => {
      if (child.type === 'dir') sortTree(child);
    });

    return node;
  }

  /**
   * Compute directory status from children.
   * Priority: new > modified > read > null
   */
  function computeDirStatus(children) {
    if (!children || children.length === 0) return null;

    const priority = { new: 3, modified: 2, read: 1 };
    let highest = 0;
    let highestStatus = null;

    for (const child of children) {
      const status = child.type === 'dir' ? child.status : child.status;
      const p = priority[status] || 0;
      if (p > highest) {
        highest = p;
        highestStatus = status;
      }
    }

    return highestStatus;
  }

  // ── Expand/Collapse State ───────────────────────────────────────

  /**
   * Track expanded state separately so it persists across tree rebuilds.
   * Key: directory path, Value: boolean (true = expanded).
   * Directories default to expanded.
   */
  const expandedDirs = ref({});

  function isExpanded(dirPath) {
    // Default to expanded if not explicitly set
    return expandedDirs.value[dirPath] !== false;
  }

  function toggleExpand(node) {
    if (node.type !== 'dir') return;
    const current = isExpanded(node.path);
    expandedDirs.value = { ...expandedDirs.value, [node.path]: !current };
  }

  // ── Event Handlers ──────────────────────────────────────────────

  function onFileRead(event) {
    const payload = event.payload || event;
    const path = payload.path;
    if (!path) return;

    const existing = fileMap.value[path];
    const name = path.split('/').pop();

    if (existing) {
      // Don't downgrade status: modified/new stays
      const updated = {
        ...existing,
        reads: existing.reads + 1,
        lastEvent: payload,
      };
      if (existing.status !== 'modified' && existing.status !== 'new') {
        updated.status = 'read';
      }
      fileMap.value = { ...fileMap.value, [path]: updated };
    } else {
      fileMap.value = {
        ...fileMap.value,
        [path]: {
          path,
          name,
          type: 'file',
          status: 'read',
          reads: 1,
          writes: 0,
          lastEvent: payload,
          diffs: [],
        },
      };
    }
  }

  function onFileWrite(event) {
    const payload = event.payload || event;
    const path = payload.path;
    if (!path) return;

    const existing = fileMap.value[path];
    const name = path.split('/').pop();
    const status = payload.is_new_file ? 'new' : 'modified';

    if (existing) {
      const diffs = [...existing.diffs];
      if (payload.diff) diffs.push(payload.diff);
      fileMap.value = {
        ...fileMap.value,
        [path]: {
          ...existing,
          status,
          writes: existing.writes + 1,
          lastEvent: payload,
          diffs,
        },
      };
    } else {
      fileMap.value = {
        ...fileMap.value,
        [path]: {
          path,
          name,
          type: 'file',
          status,
          reads: 0,
          writes: 1,
          lastEvent: payload,
          diffs: payload.diff ? [payload.diff] : [],
        },
      };
    }
  }

  // ── Actions ─────────────────────────────────────────────────────

  function selectFile(path) {
    selectedFile.value = path;
  }

  function clearFiles() {
    fileMap.value = {};
    selectedFile.value = null;
    expandedDirs.value = {};
  }

  // ── Subscriptions ───────────────────────────────────────────────
  bus.on('file.read', onFileRead);
  bus.on('file.write', onFileWrite);

  return {
    // State
    fileMap,
    selectedFile,
    // Computed
    tree,
    flatTree,
    selectedFileData,
    fileCount,
    modifiedCount,
    // Actions
    selectFile,
    toggleExpand,
    isExpanded,
    clearFiles,
  };
}
```

- [ ] **Step 2: Verify the file was created correctly**

Run: `ls -la ui/js/files.js`
Expected: File exists, ~250 lines

- [ ] **Step 3: Commit**

```bash
git add ui/js/files.js
git commit -m "feat(phase5): add useFiles composable for file explorer"
```

---

### Task 2: File Explorer CSS

**Files:**
- Create: `ui/css/files.css`

Styles for the file tree in the sidebar and the file explorer main panel. Uses design tokens from `ui/css/tokens.css`. The diff viewer styles already exist in `ui/css/tools.css` and are reused.

- [ ] **Step 1: Create `ui/css/files.css`**

Create `ui/css/files.css`:

```css
/* ============================================
   File Explorer — Phase 5
   Tree view, badges, and main panel styles
   ============================================ */

/* ── File Tree (sidebar) ─────────────────── */

.file-tree {
  font-family: var(--font-mono);
  font-size: 12px;
  padding: 4px 0;
}

.file-tree-node {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  cursor: pointer;
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  transition: background 0.15s ease, color 0.15s ease;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-tree-node:hover {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.file-tree-node.selected {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.file-tree-node svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  opacity: 0.6;
}

.file-tree-node:hover svg {
  opacity: 0.9;
}

.file-tree-chevron {
  width: 12px;
  height: 12px;
  transition: transform 0.15s ease;
  flex-shrink: 0;
}

.file-tree-chevron.expanded {
  transform: rotate(90deg);
}

.file-tree-node-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Status Badges ───────────────────────── */

.file-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 0 5px;
  border-radius: 3px;
  line-height: 16px;
  flex-shrink: 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.file-badge--modified {
  background: rgba(245, 158, 11, 0.15);
  color: var(--accent-amber);
}

.file-badge--new {
  background: rgba(34, 197, 94, 0.15);
  color: var(--accent-green);
}

.file-badge--read {
  background: transparent;
  color: var(--text-muted);
  opacity: 0.6;
}

/* ── File Explorer Main Panel ────────────── */

.file-explorer-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.file-explorer-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--bg-elevated);
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-primary);
  flex-shrink: 0;
}

.file-explorer-header-path {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-explorer-header-stats {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.file-explorer-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 0;
}

.file-explorer-body::-webkit-scrollbar {
  width: 4px;
}

.file-explorer-body::-webkit-scrollbar-thumb {
  background: var(--bg-elevated);
  border-radius: 2px;
}

.file-explorer-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  font-family: var(--font-sans);
  gap: 8px;
}

.file-explorer-empty svg {
  width: 48px;
  height: 48px;
  opacity: 0.3;
}

.file-explorer-empty-title {
  font-size: 14px;
}

.file-explorer-empty-subtitle {
  font-size: 12px;
  opacity: 0.7;
}

/* ── Diff Section in Explorer ────────────── */

.file-explorer-diff-section {
  margin: 0 16px 16px;
}

.file-explorer-diff-label {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 6px;
  padding: 0 4px;
}

/* ── Read-Only Info ──────────────────────── */

.file-explorer-read-info {
  margin: 16px;
  padding: 12px 16px;
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  font-family: var(--font-sans);
  font-size: 13px;
  color: var(--text-secondary);
}

.file-explorer-read-info-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.file-explorer-preview {
  margin-top: 8px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
```

- [ ] **Step 2: Verify the file was created correctly**

Run: `ls -la ui/css/files.css`
Expected: File exists

- [ ] **Step 3: Commit**

```bash
git add ui/css/files.css
git commit -m "feat(phase5): add file explorer CSS styles"
```

---

### Task 3: Wire `useFiles` into `app.js`

**Files:**
- Modify: `ui/js/app.js:10,27,163,228`

Import the `useFiles` composable, initialize it alongside the other composables, remove the empty `files` ref, and expose the file explorer state to the template.

- [ ] **Step 1: Add import for `useFiles`**

In `ui/js/app.js`, after line 10 (`import { useTools } from './tools.js';`), add:

```javascript
import { useFiles } from './files.js';
```

- [ ] **Step 2: Remove the empty `files` ref**

In `ui/js/app.js`, delete line 27:

```javascript
    const files = ref([]);
```

- [ ] **Step 3: Initialize `useFiles` composable**

In `ui/js/app.js`, after line 163 (`const tools = useTools(bus);`), add:

```javascript
    const filesExplorer = useFiles(bus);
```

- [ ] **Step 4: Update the return object**

In `ui/js/app.js`, in the return block (starting at line 223), replace:

```javascript
      files,
```

with:

```javascript
      filesExplorer,
```

The full return block should now include `filesExplorer` instead of `files`. The template will access `filesExplorer.tree`, `filesExplorer.selectedFile`, etc.

- [ ] **Step 5: Verify no syntax errors**

Run: `python -m pytest tests/ -v --tb=short 2>&1 | tail -5`
Expected: All 139 tests still pass (no backend changes, just verifying nothing broke)

- [ ] **Step 6: Commit**

```bash
git add ui/js/app.js
git commit -m "feat(phase5): wire useFiles composable into app"
```

---

### Task 4: Sidebar File Tree in `index.html`

**Files:**
- Modify: `ui/index.html:13-19` (CSS links)
- Modify: `ui/index.html:145-175` (sidebar Files accordion)

Replace the placeholder sidebar file tree with a recursive tree renderer that uses `filesExplorer` data.

- [ ] **Step 1: Add `files.css` link**

In `ui/index.html`, after line 19 (`<link rel="stylesheet" href="/css/tools.css" />`), add:

```html
  <link rel="stylesheet" href="/css/files.css" />
```

- [ ] **Step 2: Replace the sidebar Files accordion content**

Since Vue 3 CDN templates don't support recursive components, `useFiles` provides a `flatTree` computed that flattens the tree with depth info for simple `v-for` rendering.

In `ui/index.html`, replace lines 145-175 (the entire `<!-- SECTION: Files -->` accordion section) with:

```html
        <!-- SECTION: Files -->
        <div class="accordion-section">
          <button class="accordion-trigger" aria-expanded="true" onclick="toggleAccordion(this)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
            Files
            <span class="accordion-trigger-count">{{ filesExplorer.fileCount.value > 0 ? filesExplorer.fileCount.value : '0' }}</span>
          </button>
          <div class="accordion-body" aria-hidden="false" style="max-height: 400px;">
            <div class="file-tree">
              <div v-if="filesExplorer.fileCount.value === 0" style="padding: 10px; font-size: 11px; color: var(--text-muted); text-align: center;">
                No files
              </div>
              <div
                v-for="node in filesExplorer.flatTree.value"
                :key="node.path"
                class="file-tree-node"
                :class="{ selected: node.type === 'file' && filesExplorer.selectedFile.value === node.path }"
                :style="{ paddingLeft: (node.depth * 16 + 8) + 'px' }"
                @click="node.type === 'dir' ? filesExplorer.toggleExpand(node) : (filesExplorer.selectFile(node.path), setActivePanel('files'))"
              >
                <!-- Chevron for directories -->
                <svg
                  v-if="node.type === 'dir'"
                  class="file-tree-chevron"
                  :class="{ expanded: filesExplorer.isExpanded(node.path) }"
                  viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                >
                  <polyline points="9 18 15 12 9 6"></polyline>
                </svg>
                <!-- Spacer for files (aligns with chevron) -->
                <span v-else style="width: 12px; display: inline-block;"></span>

                <!-- Folder icon -->
                <svg v-if="node.type === 'dir'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"></path>
                </svg>
                <!-- File icon -->
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"></path>
                  <polyline points="13 2 13 9 20 9"></polyline>
                </svg>

                <!-- Name -->
                <span class="file-tree-node-name">{{ node.name }}</span>

                <!-- Status badge -->
                <span v-if="node.status === 'modified'" class="file-badge file-badge--modified">M</span>
                <span v-else-if="node.status === 'new'" class="file-badge file-badge--new">N</span>
                <span v-else-if="node.status === 'read'" class="file-badge file-badge--read">R</span>
              </div>
            </div>
          </div>
        </div>
```

- [ ] **Step 3: Verify no syntax errors in HTML**

Open `ui/index.html` in a browser or run a quick check:

Run: `python -c "with open('ui/index.html') as f: content = f.read(); print(f'HTML length: {len(content)} chars, lines: {content.count(chr(10)) + 1}')"`
Expected: File is valid, roughly 660-680 lines

- [ ] **Step 4: Commit**

```bash
git add ui/index.html
git commit -m "feat(phase5): add sidebar file tree with recursive rendering"
```

---

### Task 5: Main Content Files Panel in `index.html`

**Files:**
- Modify: `ui/index.html:581-589` (Files panel placeholder)

Replace the "Coming in Phase 5" placeholder with the actual file explorer panel showing diffs and file info.

- [ ] **Step 1: Replace the Files panel placeholder**

In `ui/index.html`, replace lines 581-589 (the placeholder `<div class="terminal-body" v-show="activePanel === 'files'" ...>` block) with:

```html
      <div class="terminal-body" v-show="activePanel === 'files'">
        <div class="file-explorer-panel">

          <!-- Empty state: no file selected -->
          <div v-if="!filesExplorer.selectedFileData.value" class="file-explorer-empty">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"></path>
            </svg>
            <div class="file-explorer-empty-title">File Explorer</div>
            <div class="file-explorer-empty-subtitle">Select a file from the sidebar to view details</div>
          </div>

          <!-- File selected -->
          <template v-else>
            <!-- Header -->
            <div class="file-explorer-header">
              <span class="file-explorer-header-path">{{ filesExplorer.selectedFileData.value.path }}</span>
              <span v-if="filesExplorer.selectedFileData.value.status === 'modified'" class="file-badge file-badge--modified">M</span>
              <span v-else-if="filesExplorer.selectedFileData.value.status === 'new'" class="file-badge file-badge--new">N</span>
              <span v-else-if="filesExplorer.selectedFileData.value.status === 'read'" class="file-badge file-badge--read">R</span>
              <div class="file-explorer-header-stats">
                <span v-if="filesExplorer.selectedFileData.value.reads > 0">{{ filesExplorer.selectedFileData.value.reads }} read{{ filesExplorer.selectedFileData.value.reads !== 1 ? 's' : '' }}</span>
                <span v-if="filesExplorer.selectedFileData.value.writes > 0">{{ filesExplorer.selectedFileData.value.writes }} write{{ filesExplorer.selectedFileData.value.writes !== 1 ? 's' : '' }}</span>
              </div>
            </div>

            <!-- Body -->
            <div class="file-explorer-body">

              <!-- Diffs (for modified/new files) -->
              <template v-if="filesExplorer.selectedFileData.value.diffs.length > 0">
                <div
                  v-for="(diff, idx) in filesExplorer.selectedFileData.value.diffs"
                  :key="idx"
                  class="file-explorer-diff-section"
                >
                  <div class="file-explorer-diff-label">Change {{ idx + 1 }} of {{ filesExplorer.selectedFileData.value.diffs.length }}</div>
                  <div class="file-diff-viewer file-diff--expanded">
                    <div class="file-diff-body">
                      <div
                        v-for="(line, lineIdx) in tools.parseDiffLines(diff)"
                        :key="lineIdx"
                        class="file-diff-line"
                        :class="'file-diff-line--' + line.type"
                      >
                        <span class="file-diff-line-number">{{ line.number }}</span>
                        <span class="file-diff-line-content">{{ line.content }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- Read-only info (no diffs) -->
              <div v-else class="file-explorer-read-info">
                <div class="file-explorer-read-info-label">File was read</div>
                <div>{{ filesExplorer.selectedFileData.value.path }}</div>
                <div
                  v-if="filesExplorer.selectedFileData.value.lastEvent && filesExplorer.selectedFileData.value.lastEvent.preview"
                  class="file-explorer-preview"
                >{{ filesExplorer.selectedFileData.value.lastEvent.preview }}</div>
              </div>

            </div>
          </template>

        </div>
      </div>
```

Note: This uses `tools.parseDiffLines(diff)` which is already available in the template since `tools` is returned from `setup()` in `app.js`.

- [ ] **Step 2: Verify the HTML structure**

Run: `python -c "with open('ui/index.html') as f: content = f.read(); print(f'HTML length: {len(content)} chars, lines: {content.count(chr(10)) + 1}')"`
Expected: File is roughly 720-740 lines

- [ ] **Step 3: Commit**

```bash
git add ui/index.html
git commit -m "feat(phase5): add file explorer main panel with diff viewer"
```

---

### Task 6: Integration Verification

**Files:**
- None (verification only)

Verify that all existing tests still pass and the file explorer works end-to-end.

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All 139 tests pass. No new tests are added (no backend changes, CDN-based frontend has no JS test runner).

- [ ] **Step 2: Verify all new files exist**

Run: `ls -la ui/js/files.js ui/css/files.css`
Expected: Both files exist

- [ ] **Step 3: Verify app.js imports are correct**

Run: `head -12 ui/js/app.js`
Expected: Shows imports for EventBus, usePipeline, useGates, useTools, useFiles

- [ ] **Step 4: Verify CSS link is in index.html**

Run: `grep 'files.css' ui/index.html`
Expected: `<link rel="stylesheet" href="/css/files.css" />`

- [ ] **Step 5: Verify no "Coming in Phase 5" placeholder remains**

Run: `grep -c "Coming in Phase 5" ui/index.html`
Expected: `0` (placeholder has been replaced)

- [ ] **Step 6: Verify sidebar tree references filesExplorer**

Run: `grep -c "filesExplorer" ui/index.html`
Expected: At least 10 occurrences (tree, selectedFile, selectFile, toggleExpand, etc.)

- [ ] **Step 7: Final commit (if any uncommitted changes)**

```bash
git status
# If clean, no commit needed
```
