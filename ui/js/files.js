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
      const status = child.status;
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
    const status = payload.is_new_file
      ? 'new'
      : existing && existing.status === 'new'
        ? 'new'
        : 'modified';

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
