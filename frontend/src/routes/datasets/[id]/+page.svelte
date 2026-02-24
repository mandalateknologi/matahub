<script lang="ts">
  import { onMount } from "svelte";
  import { navigate } from "../../../lib/router";
  import { location } from "svelte-spa-router";
  import { datasetsAPI } from "../../../lib/api/datasets";
  import { uiStore } from "../../../lib/stores/uiStore";
  import ImageGallery from "../../../lib/components/datasets/ImageGallery.svelte";
  import GalleryToolbar from "../../../lib/components/datasets/GalleryToolbar.svelte";
  import ImageUploadZone from "../../../lib/components/datasets/ImageUploadZone.svelte";
  import BoundingBoxEditor from "../../../lib/components/datasets/BoundingBoxEditor.svelte";
  import SegmentationEditor from "../../../lib/components/datasets/SegmentationEditor.svelte";
  import type {
    DatasetDetail,
    DatasetFile,
    DatasetFilesResponse,
  } from "@/lib/types";

  export let id: number | undefined = undefined;

  let dataset: DatasetDetail | null = null;
  let loading = false;
  let saving = false;
  let uploading = false;
  let validating = false;
  let rescanning = false;
  let distributing = false;
  let showDistributeModal = false;
  let distributionSeed = "";

  let editMode = false;
  let formData = {
    name: "",
    description: "",
    classes: {} as { [key: string]: string },
  };

  let newClassName = "";
  let editingClassId: string | null = null;
  let uploadFile: File | null = null;
  let showDeleteModal = false;

  let currentSplit: "train" | "val" | "test" = "train";
  let currentClass: string | null = null;
  let availableClasses: string[] = [];
  let files: DatasetFile[] = [];
  let filesTotal = 0;
  let filesHasMore = false;
  let filesLoading = false;
  let filesSkip = 0;
  const FILES_LIMIT = 100; // Increased from 50 to 100

  let splitCounts = { train: 0, val: 0, test: 0 };
  let classCounts: {
    [className: string]: { train: number; val: number; test: number };
  } = {};

  let showLabelEditor = false;
  let currentLabelFile: DatasetFile | null = null;
  let labeledFiles: Set<string> = new Set();

  // Search, filter, and sort state
  let searchTerm = "";
  let sortBy = "name_asc";
  let labelFilter = "all";

  // Scroll position tracking
  let savedScrollPosition = 0;
  let scrollRestorePending = false;

  // Recently uploaded/edited tracking
  let recentlyUploadedPaths: Set<string> = new Set();
  let recentlyEditedPaths: Set<string> = new Set();

  // Extract id from URL path and load dataset
  $: if ($location) {
    const match = $location.match(/^\/datasets\/(\d+)/);
    if (match && match[1]) {
      const parsedId = parseInt(match[1]);
      if (parsedId !== id) {
        id = parsedId;
        console.log("Extracted id from URL:", id);
        if (id && !isNaN(id) && id > 0) {
          loadDataset();
        }
      }
    }
  }

  onMount(() => {
    console.log("DatasetDetail mounted");
  });

  async function loadDataset() {
    loading = true;
    try {
      dataset = await datasetsAPI.get(id);
      formData = {
        name: dataset.name,
        description: dataset.description || "",
        classes: { ...dataset.classes_json },
      };

      await updateSplitCounts();
      await updateClassCounts();

      if (dataset.images_count > 0) {
        await loadFiles();
      }
    } catch (error) {
      uiStore.showToast("Failed to load dataset", "error");
      console.error("Error loading dataset:", error);
    } finally {
      loading = false;
    }
  }

  async function loadLabeledFiles() {
    if (
      !dataset ||
      (dataset.task_type !== "detect" && dataset.task_type !== "segment")
    )
      return;

    // Check which files have labels by checking if label files exist
    // Use Promise.all for parallel requests
    const labelChecks = files.map(async (file) => {
      try {
        const labelData = await datasetsAPI.getImageLabels(id, file.path);
        if (
          dataset.task_type === "detect" &&
          labelData.boxes &&
          labelData.boxes.length > 0
        ) {
          return file.path;
        }
        if (
          dataset.task_type === "segment" &&
          labelData.polygons &&
          labelData.polygons.length > 0
        ) {
          return file.path;
        }
      } catch (error) {
        // File doesn't have labels or error loading
      }
      return null;
    });

    const results = await Promise.all(labelChecks);
    const labeled = new Set<string>(
      results.filter((path) => path !== null) as string[]
    );
    labeledFiles = labeled;
  }

  async function loadFiles(append = false) {
    if (!dataset) return;

    filesLoading = true;
    try {
      const response: DatasetFilesResponse = await datasetsAPI.listFiles(
        id,
        currentSplit,
        currentClass || undefined,
        FILES_LIMIT,
        append ? filesSkip : 0,
        searchTerm,
        sortBy,
        labelFilter
      );

      if (
        dataset.task_type === "classify" &&
        !currentClass &&
        response.classes
      ) {
        availableClasses = response.classes;
        files = [];
        filesTotal = 0;
        filesHasMore = false;
      } else {
        if (append) {
          // Deduplicate files by path to prevent duplicate key errors
          const existingPaths = new Set(files.map((f) => f.path));
          const newFiles = response.files.filter(
            (f) => !existingPaths.has(f.path)
          );

          // If no new files were added, we've reached the end or there's duplicate data
          if (newFiles.length === 0) {
            filesHasMore = false;
          } else {
            files = [...files, ...newFiles];
            // Update filesSkip to match actual number of files we have
            filesSkip = files.length;
            // Check if we've loaded all files
            filesHasMore = response.has_more && files.length < response.total;
          }
        } else {
          // Deduplicate response files even on initial load
          const uniqueFiles = new Map();
          response.files.forEach((f) => {
            if (!uniqueFiles.has(f.path)) {
              uniqueFiles.set(f.path, f);
            }
          });
          files = Array.from(uniqueFiles.values());
          filesSkip = files.length;
          filesHasMore = response.has_more && files.length < response.total;
        }
        filesTotal = response.total;
      }

      await updateSplitCounts();

      // Load labeled files for detection and segmentation tasks
      if (
        dataset &&
        (dataset.task_type === "detect" || dataset.task_type === "segment")
      ) {
        await loadLabeledFiles();
      }
    } catch (error) {
      uiStore.showToast("Failed to load files", "error");
      console.error("Error loading files:", error);
    } finally {
      filesLoading = false;
    }
  }

  async function updateSplitCounts(forceAllClasses = false) {
    if (!dataset) return;
    try {
      // When forceAllClasses is true, don't filter by class (for distribution modal)
      const classFilter = forceAllClasses
        ? undefined
        : currentClass || undefined;

      const trainRes = await datasetsAPI.listFiles(
        id,
        "train",
        classFilter,
        1,
        0
      );
      const valRes = await datasetsAPI.listFiles(id, "val", classFilter, 1, 0);
      const testRes = await datasetsAPI.listFiles(
        id,
        "test",
        classFilter,
        1,
        0
      );

      splitCounts = {
        train: trainRes.total,
        val: valRes.total,
        test: testRes.total,
      };
    } catch (error) {
      console.error("Failed to update split counts:", error);
    }
  }

  async function updateClassCounts() {
    if (!dataset || dataset.task_type !== "classify") return;

    try {
      const counts: {
        [className: string]: { train: number; val: number; test: number };
      } = {};

      // Fetch counts for each class per split
      for (const className of Object.values(dataset.classes_json)) {
        // Count images in train, val, and test for this class
        const trainRes = await datasetsAPI.listFiles(
          id,
          "train",
          className,
          1,
          0
        );
        const valRes = await datasetsAPI.listFiles(id, "val", className, 1, 0);
        const testRes = await datasetsAPI.listFiles(
          id,
          "test",
          className,
          1,
          0
        );

        counts[className] = {
          train: trainRes.total,
          val: valRes.total,
          test: testRes.total,
        };
      }

      classCounts = counts;
    } catch (error) {
      console.error("Failed to update class counts:", error);
    }
  }

  async function handleLoadMore() {
    // filesSkip is already set to current files.length in loadFiles
    await loadFiles(true);
  }

  async function handleDeleteFile(file: DatasetFile) {
    try {
      await datasetsAPI.deleteFile(id, file.path);
      uiStore.showToast("Image deleted successfully", "success");
      await loadFiles();
      await loadDataset();
    } catch (error) {
      uiStore.showToast("Failed to delete image", "error");
      console.error("Error deleting file:", error);
    }
  }

  async function handleFilesSelected(event: CustomEvent<File[]>) {
    const selectedFiles = event.detail;

    if (!dataset) return;

    if (dataset.task_type === "classify" && !currentClass) {
      uiStore.showToast("Please select a class folder first", "error");
      return;
    }

    // Save scroll position before upload
    savedScrollPosition = window.scrollY;
    scrollRestorePending = true;

    uploading = true;
    try {
      const result = await datasetsAPI.uploadImages(
        id,
        selectedFiles,
        currentSplit,
        currentClass || undefined
      );

      if (result.total_uploaded > 0) {
        uiStore.showToast(
          `${result.total_uploaded} image(s) uploaded successfully`,
          "success"
        );

        // Track recently uploaded files
        if (result.uploaded_files && result.uploaded_files.length > 0) {
          result.uploaded_files.forEach((fileName: string) => {
            const filePath = `images/${currentSplit}/${fileName}`;
            recentlyUploadedPaths.add(filePath);
          });
          recentlyUploadedPaths = new Set(recentlyUploadedPaths);

          // Clear highlights after 5 seconds
          setTimeout(() => {
            recentlyUploadedPaths.clear();
            recentlyUploadedPaths = new Set(recentlyUploadedPaths);
          }, 5000);
        }
      }

      if (result.total_errors > 0) {
        uiStore.showToast(
          `${result.total_errors} image(s) failed to upload`,
          "error"
        );
      }

      await loadFiles();
      await loadDataset();

      // Restore scroll position after files load
      if (scrollRestorePending) {
        setTimeout(() => {
          window.scrollTo({ top: savedScrollPosition, behavior: "smooth" });
          scrollRestorePending = false;
        }, 100);
      }
    } catch (error) {
      uiStore.showToast("Failed to upload images", "error");
      console.error("Error uploading images:", error);
      scrollRestorePending = false;
    } finally {
      uploading = false;
    }
  }

  function handleSplitChange(split: "train" | "val" | "test") {
    currentSplit = split;
    filesSkip = 0;
    if (dataset && dataset.images_count > 0) {
      loadFiles();
    }
  }

  function handleClassChange(className: string | null) {
    currentClass = className;
    filesSkip = 0;
    loadFiles();
  }

  function toggleEditMode() {
    if (editMode) {
      if (dataset) {
        formData = {
          name: dataset.name,
          description: dataset.description || "",
          classes: { ...dataset.classes_json },
        };
      }
    }
    editMode = !editMode;
  }

  async function handleSave() {
    if (!dataset) return;

    saving = true;
    try {
      const updates: any = {};

      if (formData.name !== dataset.name) {
        updates.name = formData.name;
      }
      if (formData.description !== dataset.description) {
        updates.description = formData.description;
      }
      if (
        JSON.stringify(formData.classes) !==
        JSON.stringify(dataset.classes_json)
      ) {
        updates.classes_json = formData.classes;
      }

      if (Object.keys(updates).length > 0) {
        dataset = await datasetsAPI.update(id, updates);
        uiStore.showToast("Dataset updated successfully", "success");
        editMode = false;

        if (updates.classes_json) {
          await loadFiles();
        }
      } else {
        uiStore.showToast("No changes to save", "info");
        editMode = false;
      }
    } catch (error: any) {
      if (error.response?.data?.warnings) {
        const warnings = error.response.data.warnings;
        uiStore.showToast(
          `Updated with warnings: ${warnings.join(", ")}`,
          "warning"
        );
        await loadDataset();
        editMode = false;
      } else {
        uiStore.showToast("Failed to update dataset", "error");
        console.error("Error updating dataset:", error);
      }
    } finally {
      saving = false;
    }
  }

  function addNewClass() {
    if (!newClassName.trim()) return;
    const existingIds = Object.keys(formData.classes).map((id) => parseInt(id));
    const nextId = existingIds.length > 0 ? Math.max(...existingIds) + 1 : 0;
    formData.classes[nextId.toString()] = newClassName.trim();
    formData.classes = { ...formData.classes };
    newClassName = "";
  }

  function startEditClass(classId: string) {
    editingClassId = classId;
  }

  function saveClassEdit(classId: string, newName: string) {
    if (newName.trim()) {
      formData.classes[classId] = newName.trim();
      formData.classes = { ...formData.classes };
    }
    editingClassId = null;
  }

  function removeClass(classId: string) {
    delete formData.classes[classId];
    formData.classes = { ...formData.classes };
  }

  function handleFileSelect(event: Event) {
    const target = event.target as HTMLInputElement;
    if (target.files && target.files.length > 0) {
      uploadFile = target.files[0];
    }
  }

  async function handleFileUpload() {
    if (!uploadFile || !dataset) return;

    uploading = true;
    try {
      await datasetsAPI.update(id, { file: uploadFile });
      uiStore.showToast("File uploaded successfully", "success");
      uploadFile = null;
      await loadDataset();
      await loadFiles();
    } catch (error) {
      uiStore.showToast("Failed to upload file", "error");
      console.error("Error uploading file:", error);
    } finally {
      uploading = false;
    }
  }

  async function handleDelete() {
    if (!dataset) return;
    try {
      await datasetsAPI.delete(id);
      uiStore.showToast("Dataset deleted successfully", "success");
      navigate("/datasets");
    } catch (error) {
      uiStore.showToast("Failed to delete dataset", "error");
      console.error("Error deleting dataset:", error);
    }
  }

  function getStatusBadgeClass(status: string): string {
    switch (status) {
      case "empty":
        return "status-empty";
      case "incomplete":
        return "status-incomplete";
      case "valid":
        return "status-valid";
      default:
        return "";
    }
  }

  function getStatusText(status: string): string {
    switch (status) {
      case "empty":
        return "Empty";
      case "incomplete":
        return "Incomplete";
      case "valid":
        return "Valid";
      default:
        return status;
    }
  }

  async function handleRecalculateStats() {
    if (!dataset) return;

    try {
      const result = await datasetsAPI.recalculateStats(id);
      uiStore.showToast(
        "Dataset statistics recalculated successfully",
        "success"
      );
      await loadDataset();
    } catch (error) {
      uiStore.showToast("Failed to recalculate statistics", "error");
      console.error("Error recalculating stats:", error);
    }
  }

  async function handleValidate() {
    if (!dataset) return;

    validating = true;
    try {
      const result = await datasetsAPI.validate(id);

      if (result.success) {
        let message = result.message;
        if (result.warnings && result.warnings.length > 0) {
          message += "\n\nWarnings:\n" + result.warnings.join("\n");
        }
        uiStore.showToast(message, "success");
        await loadDataset();
      } else {
        let message = result.message;
        if (result.errors && result.errors.length > 0) {
          message += "\n\nErrors:\n" + result.errors.join("\n");
        }
        if (result.warnings && result.warnings.length > 0) {
          message += "\n\nWarnings:\n" + result.warnings.join("\n");
        }
        uiStore.showToast(message, "error");
      }
    } catch (error) {
      uiStore.showToast("Failed to validate dataset", "error");
      console.error("Error validating dataset:", error);
    } finally {
      validating = false;
    }
  }

  async function handleRescanClasses() {
    if (!dataset) return;

    rescanning = true;
    try {
      const result = await datasetsAPI.rescanClasses(id, [
        "train",
        "val",
        "test",
      ]);

      if (result.success) {
        uiStore.showToast(result.message, "success");

        if (result.new_classes && result.new_classes.length > 0) {
          const classNames = result.new_classes.map((c) => c.name).join(", ");
          uiStore.showToast(`Discovered classes: ${classNames}`, "info");
        }

        await loadDataset();
      } else {
        uiStore.showToast("Failed to rescan classes", "error");
      }
    } catch (error: any) {
      const errorMsg =
        error.response?.data?.detail ||
        error.message ||
        "Failed to rescan classes";
      uiStore.showToast(errorMsg, "error");
      console.error("Error rescanning classes:", error);
    } finally {
      rescanning = false;
    }
  }

  async function handleDistribute() {
    if (!dataset) return;

    distributing = true;
    try {
      const seed =
        distributionSeed.trim() !== "" ? parseInt(distributionSeed) : undefined;

      const result = await datasetsAPI.distributeImages(id, seed);

      if (result.already_optimal) {
        uiStore.showToast(result.message, "info");
        showDistributeModal = false;
      } else if (result.success) {
        const dist = result.distribution;
        const pct = result.percentages;
        const message = `Distributed ${dist.train + dist.val + dist.test} images: ${dist.train} train (${pct?.train}%), ${dist.val} val (${pct?.val}%), ${dist.test} test (${pct?.test}%)`;
        uiStore.showToast(message, "success");

        if (result.warnings && result.warnings.length > 0) {
          result.warnings.forEach((warning: string) => {
            uiStore.showToast(warning, "warning");
          });
        }

        showDistributeModal = false;
        await loadDataset();
        await updateSplitCounts();
        await updateClassCounts();
        await loadFiles();
        ounts();
        await loadFiles();
      }
    } catch (error: any) {
      const errorMsg =
        error.response?.data?.detail ||
        error.message ||
        "Failed to distribute images";
      uiStore.showToast(errorMsg, "error");
      console.error("Error distributing images:", error);
    } finally {
      distributing = false;
    }
  }

  function handleLabelImage(event: CustomEvent<DatasetFile>) {
    currentLabelFile = event.detail;
    showLabelEditor = true;
  }

  function closeLabelEditor() {
    showLabelEditor = false;
    currentLabelFile = null;
    // Reload labeled files status
    loadLabeledFiles();
  }

  // Handle labels updated event from BoundingBoxEditor
  function handleLabelsUpdated(
    event: CustomEvent<{ filePath: string; boxes: any[] }>
  ) {
    const { filePath, boxes } = event.detail;

    // Update labeled files set immediately
    if (boxes && boxes.length > 0) {
      labeledFiles.add(filePath);
    } else {
      labeledFiles.delete(filePath);
    }
    labeledFiles = new Set(labeledFiles); // Trigger reactivity

    // Track recently edited file for visual highlight
    recentlyEditedPaths.add(filePath);
    recentlyEditedPaths = new Set(recentlyEditedPaths);

    // Clear highlight after 5 seconds
    setTimeout(() => {
      recentlyEditedPaths.delete(filePath);
      recentlyEditedPaths = new Set(recentlyEditedPaths);
    }, 5000);
  }

  // Handle toolbar events
  function handleSearchChange(event: CustomEvent<string>) {
    searchTerm = event.detail;
    loadFiles(false);
  }

  function handleSortChange(event: CustomEvent<string>) {
    sortBy = event.detail;
    loadFiles(false);
  }

  function handleLabelFilterChange(event: CustomEvent<string>) {
    labelFilter = event.detail;
    loadFiles(false);
  }

  function handleLabelNext() {
    if (!currentLabelFile) return;
    const currentIndex = files.findIndex(
      (f) => f.path === currentLabelFile!.path
    );
    if (currentIndex < files.length - 1) {
      currentLabelFile = files[currentIndex + 1];
    } else {
      uiStore.showToast("No more images", "info");
    }
  }

  function handleLabelPrevious() {
    if (!currentLabelFile) return;
    const currentIndex = files.findIndex(
      (f) => f.path === currentLabelFile!.path
    );
    if (currentIndex > 0) {
      currentLabelFile = files[currentIndex - 1];
    } else {
      uiStore.showToast("Already at first image", "info");
    }
  }
</script>

<div class="page">
  <div class="page-header">
    <div class="header-left">
      <button class="btn-back" on:click={() => navigate("/datasets")}>
        ← Back to Datasets
      </button>
      <h1>{dataset?.name || "Loading..."}</h1>
    </div>
    <div class="header-actions">
      {#if !editMode}
        <button class="btn btn-outline" on:click={toggleEditMode}
          >✏️ Edit</button
        >
        {#if dataset && dataset.status === "valid" && (dataset.task_type === "detect" || dataset.task_type === "classify" || dataset.task_type === "segment")}
          <button
            class="btn btn-primary"
            on:click={() => navigate(`/training/new?dataset_id=${id}`)}
          >
            🚀 Train Model
          </button>
        {/if}
      {:else}
        <button class="btn btn-outline" on:click={toggleEditMode}>Cancel</button
        >
        <button class="btn btn-primary" on:click={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save Changes"}
        </button>
      {/if}
      <button class="btn btn-danger" on:click={() => (showDeleteModal = true)}
        >🗑️ Delete</button
      >
    </div>
  </div>

  {#if loading}
    <div class="spinner-container">
      <div class="spinner"></div>
      <div class="spinner-text">Loading dataset...</div>
    </div>
  {:else if dataset}
    <div class="content-layout">
      <div class="metadata-column">
        <div class="section">
          <h2>Information</h2>
          <div class="info-list">
            <div class="info-item">
              <label>Name</label>
              {#if editMode}
                <input type="text" bind:value={formData.name} />
              {:else}
                <div class="info-value">{dataset.name}</div>
              {/if}
            </div>
            <div class="info-item">
              <label>Description</label>
              {#if editMode}
                <textarea bind:value={formData.description} rows="3"></textarea>
              {:else}
                <div class="info-value">
                  {dataset.description || "No description"}
                </div>
              {/if}
            </div>
            <div class="info-item">
              <label>Task Type</label>
              <div class="info-value">
                <span
                  class="task-badge"
                  class:classify={dataset.task_type === "classify"}
                  class:detect={dataset.task_type === "detect"}
                  class:segment={dataset.task_type === "segment"}
                >
                  {dataset.task_type === "classify"
                    ? "Classification"
                    : dataset.task_type === "segment"
                      ? "Segmentation"
                      : "Detection"}
                </span>
              </div>
            </div>
            <div class="info-item">
              <label>Status</label>
              <div class="info-value-with-action">
                <span
                  class="status-badge {getStatusBadgeClass(dataset.status)}"
                >
                  {getStatusText(dataset.status)}
                </span>
              </div>
              <button
                class="btn-validate-prominent"
                on:click={handleValidate}
                disabled={validating}
                title={dataset.status === "valid"
                  ? "Re-validate dataset to update status and counts"
                  : "Validate dataset and mark as ready for training"}
              >
                {#if validating}
                  <span class="btn-spinner"></span>
                  Validating...
                {:else if dataset.status === "valid"}
                  🔄 Re-Validate
                {:else}
                  ✓ Validate & Prepare for Training
                {/if}
              </button>
            </div>
            <div class="info-item">
              <label>Images</label>
              <div class="info-value-with-action">
                <span>{dataset.images_count}</span>
                <button
                  class="btn-recalc"
                  on:click={handleRecalculateStats}
                  title="Recalculate counts"
                >
                  🔄
                </button>
              </div>
            </div>
            <div class="info-item">
              <label>Labels</label>
              <div class="info-value">{dataset.labels_count}</div>
            </div>
            <div class="info-item">
              <label>Created</label>
              <div class="info-value">
                {new Date(dataset.created_at).toLocaleString()}
              </div>
            </div>
          </div>
        </div>

        <div class="section">
          <div class="section-header-with-action">
            <h2>Classes ({Object.keys(formData.classes).length})</h2>
            {#if dataset && dataset.task_type === "classify" && !editMode}
              <div class="button-group">
                <button
                  class="btn btn-sm btn-outline"
                  on:click={handleRescanClasses}
                  disabled={rescanning}
                  title="Scan folder structure and add missing classes"
                >
                  {#if rescanning}
                    <span class="btn-spinner-sm"></span>
                    Scanning...
                  {:else}
                    🔍 Rescan Folders
                  {/if}
                </button>
                <button
                  class="btn btn-sm btn-primary"
                  on:click={async () => {
                    await updateSplitCounts(true);
                    showDistributeModal = true;
                  }}
                  disabled={dataset.images_count === 0}
                  title="Redistribute images across train/val/test splits (80/10/10)"
                >
                  📊 Distribute
                </button>
              </div>
            {/if}
          </div>
          {#if editMode}
            <div class="class-editor">
              <div class="add-class-form">
                <input
                  type="text"
                  placeholder="New class name"
                  bind:value={newClassName}
                  on:keydown={(e) => e.key === "Enter" && addNewClass()}
                />
                <button class="btn btn-sm btn-primary" on:click={addNewClass}
                  >Add</button
                >
              </div>
              <div class="class-list">
                {#each Object.entries(formData.classes) as [classId, className]}
                  <div class="class-item">
                    <span class="class-id">{classId}</span>
                    {#if editingClassId === classId}
                      <input
                        type="text"
                        value={className}
                        on:blur={(e) =>
                          saveClassEdit(classId, e.currentTarget.value)}
                        on:keydown={(e) =>
                          e.key === "Enter" &&
                          saveClassEdit(classId, e.currentTarget.value)}
                      />
                    {:else}
                      <span
                        class="class-name"
                        on:click={() => startEditClass(classId)}
                        >{className}</span
                      >
                    {/if}
                    <button
                      class="btn-icon"
                      on:click={() => removeClass(classId)}
                      title="Remove">🗑️</button
                    >
                  </div>
                {/each}
              </div>
            </div>
          {:else}
            <div class="class-list">
              {#each Object.entries(dataset.classes_json) as [classId, className]}
                <div class="class-item">
                  <span class="class-id">{classId}</span>
                  <span class="class-name">{className}</span>
                  {#if classCounts[className] !== undefined}
                    <span class="class-count"
                      >({classCounts[className].train +
                        classCounts[className].val +
                        classCounts[className].test})</span
                    >
                  {/if}
                </div>
              {:else}
                <p class="text-muted">No classes defined yet</p>
              {/each}
            </div>
          {/if}
        </div>
      </div>

      <div class="gallery-column">
        <div class="section">
          <h2>Images</h2>

          <div class="tabs">
            <button
              class="tab"
              class:active={currentSplit === "train"}
              on:click={() => handleSplitChange("train")}
            >
              Train <span class="count-badge">{splitCounts.train || 0}</span>
            </button>
            <button
              class="tab"
              class:active={currentSplit === "val"}
              on:click={() => handleSplitChange("val")}
            >
              Val <span class="count-badge">{splitCounts.val || 0}</span>
            </button>
            <button
              class="tab"
              class:active={currentSplit === "test"}
              on:click={() => handleSplitChange("test")}
            >
              Test <span class="count-badge">{splitCounts.test || 0}</span>
            </button>
          </div>

          {#if dataset && dataset.task_type === "classify" && (availableClasses.length > 0 || Object.keys(dataset.classes_json).length > 0)}
            <div class="class-tabs">
              <button
                class="class-tab"
                class:active={currentClass === null}
                on:click={() => handleClassChange(null)}
              >
                All Classes
              </button>
              {#each Object.values(dataset.classes_json) as className}
                <button
                  class="class-tab"
                  class:active={currentClass === className}
                  on:click={() => handleClassChange(className)}
                >
                  {className}
                  {#if classCounts[className] !== undefined}
                    <span class="count-badge"
                      >{classCounts[className][currentSplit]}</span
                    >
                  {/if}
                  {#if !availableClasses.includes(className)}<span
                      class="new-badge">new</span
                    >{/if}
                </button>
              {/each}
            </div>
          {/if}

          {#if dataset && dataset.task_type === "detect"}
            <div class="upload-path-banner">
              <span class="path-icon">🗂️</span>
              <span class="path-text"
                >Uploading to: <strong>{currentSplit}</strong>/images/</span
              >
            </div>
            <div class="upload-section">
              <ImageUploadZone
                on:filesSelected={handleFilesSelected}
                disabled={uploading}
              />
            </div>
          {:else if dataset && dataset.task_type === "segment"}
            <div class="upload-path-banner">
              <span class="path-icon">🗂️</span>
              <span class="path-text"
                >Uploading to: <strong>{currentSplit}</strong>/images/</span
              >
            </div>
            <div class="upload-section">
              <ImageUploadZone
                on:filesSelected={handleFilesSelected}
                disabled={uploading}
              />
            </div>
          {:else if dataset && dataset.task_type === "classify"}
            {#if currentClass}
              <div class="upload-path-banner">
                <span class="path-icon">🗂️</span>
                <span class="path-text"
                  >Uploading to: <strong>{currentSplit}</strong>
                  <span class="path-separator">→</span>
                  <strong>{currentClass}</strong>/</span
                >
              </div>
              <div class="upload-section">
                <ImageUploadZone
                  on:filesSelected={handleFilesSelected}
                  disabled={uploading}
                />
              </div>
            {:else}
              <div class="upload-path-banner">
                <span class="path-icon">🗂️</span>
                <span class="path-text"
                  >Uploading to: <strong>{currentSplit}</strong>/
                  <span class="text-muted-inline">(Select a class below)</span
                  ></span
                >
              </div>
            {/if}
          {/if}

          {#if files.length === 0 && !filesLoading && !searchTerm && labelFilter === "all"}
            <div class="empty-gallery">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="64"
                height="64"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <polyline points="21 15 16 10 5 21"></polyline>
              </svg>
              {#if dataset && dataset.task_type === "classify" && !currentClass}
                <p>
                  No images in any class folders yet. Select a class above to
                  upload.
                </p>
              {:else if dataset && dataset.task_type === "classify" && currentClass}
                <p>No images in <strong>{currentClass}</strong> folder yet.</p>
              {:else}
                <p>
                  No images in <strong
                    >{currentSplit
                      ? currentSplit.toUpperCase()
                      : "TRAIN"}</strong
                  > folder yet.
                </p>
              {/if}
            </div>
          {:else}
            <GalleryToolbar
              {searchTerm}
              {sortBy}
              {labelFilter}
              totalFiles={filesTotal}
              filteredCount={files.length}
              taskType={dataset?.task_type || "detect"}
              on:searchChange={handleSearchChange}
              on:sortChange={handleSortChange}
              on:labelFilterChange={handleLabelFilterChange}
            />

            {#if id}
              <ImageGallery
                datasetId={id}
                {files}
                hasMore={filesHasMore}
                onLoadMore={handleLoadMore}
                onDeleteFile={handleDeleteFile}
                loading={filesLoading}
                taskType={dataset?.task_type || "detect"}
                classes={dataset?.classes_json || {}}
                {labeledFiles}
                {searchTerm}
                {sortBy}
                {labelFilter}
                recentlyUploaded={recentlyUploadedPaths}
                recentlyEdited={recentlyEditedPaths}
                on:labelImage={handleLabelImage}
                on:labelsUpdated={handleLabelsUpdated}
              />
            {/if}
          {/if}
        </div>
      </div>
    </div>
  {:else}
    <div class="empty-state">
      <h3>Dataset not found</h3>
      <p>The requested dataset could not be loaded.</p>
      <button class="btn btn-primary" on:click={() => navigate("/datasets")}
        >Back to Datasets</button
      >
    </div>
  {/if}
</div>

{#if showDeleteModal}
  <div class="modal-overlay" on:click={() => (showDeleteModal = false)}>
    <div class="modal-content" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Delete Dataset</h2>
        <button class="close-btn" on:click={() => (showDeleteModal = false)}
          >&times;</button
        >
      </div>
      <div class="modal-body">
        <p>Are you sure you want to delete <strong>{dataset?.name}</strong>?</p>
        <p class="text-error">
          This action cannot be undone. All files and data will be permanently
          deleted.
        </p>
      </div>
      <div class="modal-footer">
        <button
          class="btn btn-outline"
          on:click={() => (showDeleteModal = false)}>Cancel</button
        >
        <button class="btn btn-danger" on:click={handleDelete}
          >Delete Dataset</button
        >
      </div>
    </div>
  </div>
{/if}

{#if showLabelEditor && currentLabelFile && dataset}
  {#if dataset.task_type === "segment"}
    {#key currentLabelFile.path}
      <SegmentationEditor
        datasetId={id}
        file={currentLabelFile}
        classes={dataset.classes_json}
        onClose={closeLabelEditor}
        onNext={handleLabelNext}
        onPrevious={handleLabelPrevious}
        on:labelSaved={handleLabelsUpdated}
      />
    {/key}
  {:else}
    <BoundingBoxEditor
      datasetId={id}
      file={currentLabelFile}
      classes={dataset.classes_json}
      onClose={closeLabelEditor}
      onNext={handleLabelNext}
      onPrevious={handleLabelPrevious}
      on:labelsUpdated={handleLabelsUpdated}
    />
  {/if}
{/if}

{#if showDistributeModal && dataset}
  <div class="modal-overlay" on:click={() => (showDistributeModal = false)}>
    <div class="modal-content modal-distribute" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Distribute Images</h2>
        <button class="close-btn" on:click={() => (showDistributeModal = false)}
          >&times;</button
        >
      </div>
      <div class="modal-body">
        <div class="warning-box">
          <div class="warning-icon">⚠️</div>
          <div>
            <strong>Warning: Data Loss Risk</strong>
            <p>
              This will redistribute ALL images across train/val/test splits.
              Your current distribution will be lost.
            </p>
          </div>
        </div>

        <div class="distribution-info">
          <h3>Current Distribution</h3>
          <div class="distribution-stats">
            <div class="stat-item">
              <span class="stat-label">Train:</span>
              <span class="stat-value">{splitCounts.train} images</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Val:</span>
              <span class="stat-value">{splitCounts.val} images</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Test:</span>
              <span class="stat-value">{splitCounts.test} images</span>
            </div>
          </div>
        </div>

        <div class="distribution-info target-info">
          <h3>Target Distribution</h3>
          <p class="target-ratio">80% Train / 10% Val / 10% Test</p>
          <p class="target-note">
            Images will be randomly shuffled and distributed per class to
            maintain class balance.
          </p>
        </div>

        <div class="form-group">
          <label for="distributionSeed">
            Seed (optional)
            <span class="label-help">For reproducible distribution</span>
          </label>
          <input
            id="distributionSeed"
            type="number"
            bind:value={distributionSeed}
            placeholder="e.g., 42"
            disabled={distributing}
          />
        </div>
      </div>
      <div class="modal-footer">
        <button
          class="btn btn-outline"
          on:click={() => (showDistributeModal = false)}
          disabled={distributing}
        >
          Cancel
        </button>
        <button
          class="btn btn-warning"
          on:click={handleDistribute}
          disabled={distributing}
        >
          {#if distributing}
            <span class="btn-spinner-sm"></span>
            Distributing...
          {:else}
            Distribute Images
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if showDistributeModal && dataset}
  <div class="modal-overlay" on:click={() => (showDistributeModal = false)}>
    <div class="modal-content modal-distribute" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Distribute Images</h2>
        <button class="close-btn" on:click={() => (showDistributeModal = false)}
          >&times;</button
        >
      </div>
      <div class="modal-body">
        <div class="warning-box">
          <div class="warning-icon">⚠️</div>
          <div>
            <strong>Warning: Data Loss Risk</strong>
            <p>
              This will redistribute ALL images across train/val/test splits.
              Your current distribution will be lost.
            </p>
          </div>
        </div>

        <div class="distribution-info">
          <h3>Current Distribution</h3>
          <div class="distribution-stats">
            <div class="stat-item">
              <span class="stat-label">Train:</span>
              <span class="stat-value">{splitCounts.train} images</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Val:</span>
              <span class="stat-value">{splitCounts.val} images</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Test:</span>
              <span class="stat-value">{splitCounts.test} images</span>
            </div>
          </div>
        </div>

        <div class="distribution-info target-info">
          <h3>Target Distribution</h3>
          <p class="target-ratio">80% Train / 10% Val / 10% Test</p>
          <p class="target-note">
            Images will be randomly shuffled and distributed per class to
            maintain class balance.
          </p>
        </div>

        <div class="form-group">
          <label for="distributionSeed">
            Seed (optional)
            <span class="label-help">For reproducible distribution</span>
          </label>
          <input
            id="distributionSeed"
            type="number"
            bind:value={distributionSeed}
            placeholder="e.g., 42"
            disabled={distributing}
          />
        </div>
      </div>
      <div class="modal-footer">
        <button
          class="btn btn-outline"
          on:click={() => (showDistributeModal = false)}
          disabled={distributing}
        >
          Cancel
        </button>
        <button
          class="btn btn-warning"
          on:click={handleDistribute}
          disabled={distributing}
        >
          {#if distributing}
            <span class="btn-spinner-sm"></span>
            Distributing...
          {:else}
            Distribute Images
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if validating}
  <div class="validation-overlay">
    <div class="validation-modal">
      <div class="validation-spinner"></div>
      <h3>Validating Dataset</h3>
      <p class="validation-message">
        Checking dataset structure and requirements...
      </p>
      <div class="validation-steps">
        <div class="validation-step">
          <svg
            class="check-icon"
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          <span>Recalculating statistics</span>
        </div>
        <div class="validation-step">
          <svg
            class="check-icon"
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          <span>Verifying images and labels</span>
        </div>
        <div class="validation-step">
          <svg
            class="check-icon"
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          <span>Checking configuration files</span>
        </div>
      </div>
      <p class="validation-note">
        This may take a few moments for large datasets
      </p>
    </div>
  </div>
{/if}

<style>
  .page {
    padding: var(--spacing-lg);
    max-width: 1600px;
    margin: 0 auto;
  }
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--spacing-xl);
    flex-wrap: wrap;
    gap: var(--spacing-md);
  }
  .header-left h1 {
    margin-top: var(--spacing-sm);
    margin-bottom: 0;
  }
  .btn-back {
    background: none;
    border: none;
    color: var(--color-accent);
    font-size: var(--font-size-base);
    cursor: pointer;
    padding: var(--spacing-xs) 0;
    margin-bottom: var(--spacing-sm);
  }
  .btn-back:hover {
    text-decoration: underline;
    transform: none;
  }
  .header-actions {
    display: flex;
    gap: var(--spacing-sm);
    flex-wrap: wrap;
  }
  .btn-danger {
    background-color: var(--color-error);
    color: var(--color-white);
  }
  .content-layout {
    display: grid;
    grid-template-columns: 400px 1fr;
    gap: var(--spacing-lg);
    align-items: start;
  }
  .metadata-column {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-lg);
    position: sticky;
    top: var(--spacing-lg);
  }
  .gallery-column {
    min-height: 500px;
  }
  .section {
    background: var(--color-bg-card);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    box-shadow: var(--shadow-md);
  }
  .section h2 {
    margin-top: 0;
    margin-bottom: var(--spacing-lg);
    color: var(--color-navy);
    font-size: 1.25rem;
  }
  .section-header-with-action {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-lg);
  }
  .section-header-with-action h2 {
    margin: 0;
  }
  .button-group {
    display: flex;
    gap: var(--spacing-xs);
  }
  .btn-spinner-sm {
    width: 12px;
    height: 12px;
    border: 2px solid rgba(29, 47, 67, 0.2);
    border-top-color: var(--color-navy);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    display: inline-block;
  }
  .distribute-section {
    margin-bottom: var(--spacing-lg);
  }
  .btn-distribute {
    width: 100%;
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    border: 2px solid #3b82f6;
    border-radius: var(--radius-md);
    padding: 0.875rem 1.5rem;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-fast);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
  }
  .btn-distribute:hover:not(:disabled) {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    border-color: #2563eb;
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.4);
  }
  .btn-distribute:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }
  .modal-distribute {
    max-width: 600px;
  }
  .warning-box {
    display: flex;
    gap: var(--spacing-md);
    padding: var(--spacing-md);
    background: #fef3c7;
    border: 2px solid #f59e0b;
    border-radius: var(--radius-md);
    margin-bottom: var(--spacing-lg);
  }
  .warning-icon {
    font-size: 1.5rem;
    flex-shrink: 0;
  }
  .warning-box strong {
    color: #92400e;
    display: block;
    margin-bottom: 0.25rem;
  }
  .warning-box p {
    color: #78350f;
    margin: 0;
    font-size: 0.9375rem;
  }
  .distribution-info {
    margin-bottom: var(--spacing-lg);
  }
  .distribution-info h3 {
    margin: 0 0 var(--spacing-sm);
    color: var(--color-navy);
    font-size: 1.125rem;
  }
  .distribution-stats {
    display: flex;
    gap: var(--spacing-md);
    padding: var(--spacing-md);
    background: var(--color-bg-light1);
    border-radius: var(--radius-md);
  }
  .stat-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .stat-label {
    font-size: 0.875rem;
    color: var(--color-grey);
    font-weight: 600;
  }
  .stat-value {
    font-size: 1.125rem;
    color: var(--color-navy);
    font-weight: 700;
  }
  .target-info {
    background: #eff6ff;
    padding: var(--spacing-md);
    border-radius: var(--radius-md);
    border: 1px solid #bfdbfe;
  }
  .target-ratio {
    font-size: 1.25rem;
    font-weight: 700;
    color: #1e40af;
    margin: 0 0 var(--spacing-xs);
  }
  .target-note {
    margin: 0;
    font-size: 0.875rem;
    color: #1e40af;
  }
  .label-help {
    font-weight: 400;
    color: var(--color-grey);
    font-size: 0.875rem;
    margin-left: 0.5rem;
  }
  .distribute-section {
    margin-bottom: var(--spacing-lg);
  }
  .btn-distribute {
    width: 100%;
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    border: 2px solid #3b82f6;
    border-radius: var(--radius-md);
    padding: 0.875rem 1.5rem;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-fast);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
  }
  .btn-distribute:hover:not(:disabled) {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    border-color: #2563eb;
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.4);
  }
  .btn-distribute:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }
  .modal-distribute {
    max-width: 600px;
  }
  .warning-box {
    display: flex;
    gap: var(--spacing-md);
    padding: var(--spacing-md);
    background: #fef3c7;
    border: 2px solid #f59e0b;
    border-radius: var(--radius-md);
    margin-bottom: var(--spacing-lg);
  }
  .warning-icon {
    font-size: 1.5rem;
    flex-shrink: 0;
  }
  .warning-box strong {
    color: #92400e;
    display: block;
    margin-bottom: 0.25rem;
  }
  .warning-box p {
    color: #78350f;
    margin: 0;
    font-size: 0.9375rem;
  }
  .distribution-info {
    margin-bottom: var(--spacing-lg);
  }
  .distribution-info h3 {
    margin: 0 0 var(--spacing-sm);
    color: var(--color-navy);
    font-size: 1.125rem;
  }
  .distribution-stats {
    display: flex;
    gap: var(--spacing-md);
    padding: var(--spacing-md);
    background: var(--color-bg-light1);
    border-radius: var(--radius-md);
  }
  .stat-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .stat-label {
    font-size: 0.875rem;
    color: var(--color-grey);
    font-weight: 600;
  }
  .stat-value {
    font-size: 1.125rem;
    color: var(--color-navy);
    font-weight: 700;
  }
  .target-info {
    background: #eff6ff;
    padding: var(--spacing-md);
    border-radius: var(--radius-md);
    border: 1px solid #bfdbfe;
  }
  .target-ratio {
    font-size: 1.25rem;
    font-weight: 700;
    color: #1e40af;
    margin: 0 0 var(--spacing-xs);
  }
  .target-note {
    margin: 0;
    font-size: 0.875rem;
    color: #1e40af;
  }
  .form-group {
    margin-bottom: 0;
  }
  .form-group label {
    display: block;
    margin-bottom: var(--spacing-xs);
    font-weight: 600;
    color: var(--color-navy);
  }
  .label-help {
    font-weight: 400;
    color: var(--color-grey);
    font-size: 0.875rem;
    margin-left: 0.5rem;
  }
  .form-group input[type="number"] {
    width: 100%;
    padding: 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    font-size: 1rem;
  }
  .btn-warning {
    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
    color: white;
    border: 2px solid #f59e0b;
  }
  .btn-warning:hover:not(:disabled) {
    background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
    border-color: #d97706;
  }
  .info-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
  }
  .info-item {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }
  .info-item label {
    font-weight: 600;
    color: var(--color-grey);
    font-size: var(--font-size-sm);
    text-transform: uppercase;
  }
  .info-value {
    color: var(--color-navy);
    font-size: var(--font-size-base);
  }
  .info-value-with-action {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    color: var(--color-navy);
    font-size: var(--font-size-base);
  }
  .btn-recalc {
    background: none;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 0.875rem;
    padding: 2px 6px;
    opacity: 0.6;
    transition: all var(--transition-fast);
  }
  .btn-recalc:hover {
    opacity: 1;
    border-color: var(--color-primary);
    transform: scale(1.1);
  }
  .btn-validate-prominent {
    background: linear-gradient(135deg, #e1604c 0%, #c94a38 100%);
    color: white;
    border: 2px solid #e1604c;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 0.9375rem;
    padding: 0.75rem 1.5rem;
    font-weight: 700;
    transition: all var(--transition-fast);
    margin-top: 0.75rem;
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    box-shadow: 0 4px 12px rgba(225, 96, 76, 0.3);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .btn-validate-prominent:hover:not(:disabled) {
    background: linear-gradient(135deg, #1d2f43 0%, #152131 100%);
    border-color: #1d2f43;
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(29, 47, 67, 0.4);
  }
  .btn-validate-prominent:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }
  .btn-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  .task-badge {
    padding: var(--spacing-xs) var(--spacing-md);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
    background-color: var(--color-bg-light1);
    color: var(--color-navy);
    display: inline-block;
  }
  .task-badge.classify {
    background-color: #fed7aa;
    color: #c2410c;
  }
  .task-badge.detect {
    background-color: #dbeafe;
    color: #1e40af;
  }
  .task-badge.segment {
    background-color: #e9d5ff;
    color: #7c3aed;
  }
  .status-badge {
    padding: var(--spacing-xs) var(--spacing-md);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
    font-weight: 600;
    display: inline-block;
  }
  .status-badge.status-empty {
    background-color: #e0e7ff;
    color: #4338ca;
  }
  .status-badge.status-incomplete {
    background-color: #fef3c7;
    color: #b45309;
  }
  .status-badge.status-valid {
    background-color: #d1fae5;
    color: #065f46;
  }
  .class-editor {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
  }
  .add-class-form {
    display: flex;
    gap: var(--spacing-sm);
  }
  .add-class-form input {
    flex: 1;
  }
  .class-list {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm);
  }
  .class-item {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    padding: var(--spacing-sm) var(--spacing-md);
    background-color: var(--color-bg-light1);
    border-radius: var(--radius-sm);
  }
  .class-id {
    font-weight: 600;
    color: var(--color-accent);
    min-width: 30px;
    font-size: 0.875rem;
  }
  .class-name {
    flex: 1;
    cursor: text;
    font-size: 0.9375rem;
  }
  .class-count {
    font-size: 0.875rem;
    color: var(--color-grey);
    font-weight: 500;
    margin-left: auto;
  }
  .class-item input {
    flex: 1;
    padding: var(--spacing-xs) var(--spacing-sm);
  }
  .btn-icon {
    background: none;
    border: none;
    cursor: pointer;
    font-size: var(--font-size-base);
    padding: var(--spacing-xs);
    opacity: 0.6;
    transition: opacity var(--transition-fast);
  }
  .btn-icon:hover {
    opacity: 1;
    transform: none;
  }
  .upload-zone-simple {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-md);
  }
  .upload-zone-simple input[type="file"] {
    display: none;
  }
  .upload-label {
    padding: var(--spacing-sm) var(--spacing-lg);
    background-color: var(--color-navy);
    color: var(--color-white);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-base);
    font-weight: 500;
    font-size: 0.9375rem;
  }
  .upload-label:hover {
    background-color: var(--color-accent);
  }
  .selected-file {
    color: var(--color-grey);
    font-size: var(--font-size-sm);
  }
  .text-muted {
    color: var(--color-grey);
    font-size: var(--font-size-sm);
    margin: 0 0 var(--spacing-sm);
  }
  .text-info {
    color: var(--color-primary);
    font-size: var(--font-size-sm);
    margin: var(--spacing-sm) 0;
    padding: var(--spacing-sm);
    background: rgba(29, 47, 67, 0.05);
    border-radius: var(--radius-sm);
  }
  .text-info code {
    background: rgba(0, 0, 0, 0.1);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.875em;
  }
  .tabs {
    display: flex;
    gap: var(--spacing-xs);
    margin-bottom: var(--spacing-lg);
    border-bottom: 2px solid var(--color-bg-light1);
  }
  .tab {
    padding: var(--spacing-sm) var(--spacing-lg);
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--color-grey);
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition-fast);
    margin-bottom: -2px;
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
  }
  .tab:hover {
    color: var(--color-navy);
    transform: none;
  }
  .tab.active {
    color: var(--color-primary);
    border-bottom-color: var(--color-primary);
  }
  .count-badge {
    background: var(--color-bg-light1);
    color: var(--color-navy);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
  }
  .tab.active .count-badge {
    background: var(--color-primary);
    color: rgb(171, 117, 0);
  }
  .class-tabs {
    display: flex;
    gap: var(--spacing-xs);
    flex-wrap: wrap;
    margin-bottom: var(--spacing-lg);
    padding: var(--spacing-md);
    background: var(--color-bg-light1);
    border-radius: var(--radius-md);
  }
  .class-tab {
    padding: var(--spacing-xs) var(--spacing-md);
    background: var(--color-bg-primary);  
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    color: var(--color-navy);
    font-size: var(--font-size-sm);
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  .class-tab:hover {
    border-color: var(--color-primary);
    transform: none;
  }
  .class-tab.active {
    background: var(--color-primary);
    color: white;
    border-color: var(--color-primary);
  }
  .upload-section {
    margin-bottom: var(--spacing-lg);
  }
  .upload-path-banner {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-md);
    background: rgba(29, 47, 67, 0.05);
    border-radius: var(--radius-md);
    margin-bottom: var(--spacing-md);
    font-size: 0.9375rem;
  }
  .path-icon {
    font-size: 1.125rem;
  }
  .path-separator {
    opacity: 0.6;
    margin: 0 var(--spacing-xs);
  }
  .text-muted-inline {
    color: var(--color-grey);
    font-weight: 400;
    font-size: 0.875rem;
  }
  .new-badge {
    font-size: 0.625rem;
    padding: 2px 6px;
    background: #e0e7ff;
    color: #4338ca;
    border-radius: 8px;
    margin-left: 4px;
    font-weight: 600;
    text-transform: uppercase;
  }
  .empty-gallery {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    color: var(--color-text-secondary);
    text-align: center;
  }
  .empty-gallery svg {
    opacity: 0.3;
    margin-bottom: 1rem;
  }
  .empty-gallery p {
    margin: 0;
    line-height: 1.5;
  }
  .empty-gallery p strong {
    color: var(--color-primary);
    font-weight: 600;
  }
  .select-class-message {
    text-align: center;
    padding: 3rem 2rem;
    color: var(--color-grey);
    font-size: 1.125rem;
  }
  .empty-state {
    text-align: center;
    padding: var(--spacing-xl);
  }
  .empty-state h3 {
    color: var(--color-navy);
    margin-bottom: var(--spacing-sm);
  }
  .empty-state p {
    color: var(--color-grey);
    margin-bottom: var(--spacing-lg);
  }
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .modal-content {
    background: white;
    border-radius: var(--radius-lg);
    width: 90%;
    max-width: 500px;
    box-shadow: var(--shadow-xl);
  }
  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-lg);
    border-bottom: 1px solid var(--color-border);
  }
  .modal-header h2 {
    margin: 0;
    color: var(--color-navy);
  }
  .modal-body {
    padding: var(--spacing-lg);
  }
  .modal-body p {
    margin: 0 0 var(--spacing-md);
  }
  .text-error {
    color: var(--color-error);
    font-size: var(--font-size-sm);
  }
  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: var(--spacing-sm);
    padding: var(--spacing-lg);
    border-top: 1px solid var(--color-border);
  }
  .close-btn {
    background: none;
    border: none;
    font-size: 2rem;
    color: var(--color-grey);
    cursor: pointer;
    padding: 0;
    line-height: 1;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .close-btn:hover {
    color: var(--color-navy);
    transform: none;
  }
  .spinner-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem;
  }
  .spinner {
    border: 4px solid var(--color-bg-light1);
    border-top: 4px solid var(--color-primary);
    border-radius: 50%;
    width: 48px;
    height: 48px;
    animation: spin 1s linear infinite;
  }
  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }
  .spinner-text {
    margin-top: var(--spacing-md);
    color: var(--color-grey);
  }

  /* Validation Loading Modal */
  .validation-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    backdrop-filter: blur(4px);
  }

  .validation-modal {
    background: white;
    border-radius: var(--radius-lg);
    padding: 2.5rem;
    width: 90%;
    max-width: 500px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    text-align: center;
    animation: modalSlideIn 0.3s ease-out;
  }

  @keyframes modalSlideIn {
    from {
      opacity: 0;
      transform: translateY(-20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .validation-spinner {
    width: 60px;
    height: 60px;
    border: 4px solid rgba(225, 96, 76, 0.1);
    border-radius: 50%;
    border-top-color: var(--color-accent);
    animation: spin 1s linear infinite;
    margin: 0 auto 1.5rem;
  }

  .validation-modal h3 {
    margin: 0 0 0.75rem;
    font-size: 1.5rem;
    color: var(--color-navy);
    font-weight: 600;
  }

  .validation-message {
    color: var(--color-grey);
    margin: 0 0 2rem;
    font-size: 1rem;
  }

  .validation-steps {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
    text-align: left;
  }

  .validation-step {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: rgba(29, 47, 67, 0.05);
    border-radius: var(--radius-sm);
    font-size: 0.9375rem;
    color: var(--color-navy);
  }

  .validation-step .check-icon {
    color: var(--color-accent);
    flex-shrink: 0;
  }

  .validation-note {
    margin: 0;
    font-size: 0.875rem;
    color: var(--color-grey);
    font-style: italic;
  }

  @media (max-width: 1200px) {
    .content-layout {
      grid-template-columns: 350px 1fr;
    }
  }
  @media (max-width: 968px) {
    .content-layout {
      grid-template-columns: 1fr;
    }
    .metadata-column {
      position: static;
    }
  }
  @media (max-width: 768px) {
    .page {
      padding: var(--spacing-md);
    }
    .page-header {
      flex-direction: column;
      align-items: stretch;
    }
    .header-actions {
      justify-content: stretch;
    }
    .header-actions button {
      flex: 1;
    }
    .tabs {
      overflow-x: auto;
    }
    .class-tabs {
      overflow-x: auto;
    }
    .upload-path-banner {
      font-size: 0.875rem;
    }
    .upload-path-banner .path-text::before {
      content: "Target: ";
    }
    .path-separator {
      display: none;
    }
  }
</style>
