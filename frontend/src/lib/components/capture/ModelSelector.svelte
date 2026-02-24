<script lang="ts">
  /**
   * ModelSelector - Component for selecting AI models
   *
   * Extracted from capture page (Phase 1) with task-specific instructions.
   * Displays model dropdown with optional collapsible task tips.
   */

  import type { Model } from "@/lib/types";
  import type { Snippet } from "svelte";

  // Svelte 5: Props using $props() rune
  let {
    models = [],
    selectedModelId = $bindable(null),
    selectedModel = null,
    disabled = false,
    showTaskInstructions = true,
    onModelChange = undefined,
    taskWarning = undefined,
  }: {
    models?: Model[];
    selectedModelId?: number | null;
    selectedModel?: Model | null;
    disabled?: boolean;
    showTaskInstructions?: boolean;
    onModelChange?:
      | ((detail: { modelId: number; model: Model | null }) => void)
      | undefined;
    taskWarning?: Snippet<[Model]>;
  } = $props();

  let isTipsCollapsed = $state(false);

  function getTaskInstructions(taskType: string): string {
    switch (taskType) {
      case "detect":
        return "Detects and localizes objects in images using bounding boxes. Ideal for counting objects, tracking movement, or identifying object locations.";
      case "classify":
        return "Classifies entire images into predefined categories. Best for identifying image types, quality assessment, or scene recognition.";
      case "segment":
        return "Creates pixel-precise masks for objects. Use for background removal, detailed object extraction, or precise measurements.";
      default:
        return "AI model for computer vision tasks.";
    }
  }

  function getTaskFormatGuidance(taskType: string): {
    title: string;
    items: string[];
  } {
    switch (taskType) {
      case "detect":
        return {
          title: "Best Results:",
          items: [
            "Clear, well-lit images",
            "Objects fully visible in frame",
            "Avoid extreme angles or occlusions",
          ],
        };
      case "classify":
        return {
          title: "Best Results:",
          items: [
            "Image represents one clear subject",
            "Good lighting and focus",
            "Subject centered in frame",
          ],
        };
      case "segment":
        return {
          title: "Best Results:",
          items: [
            "High contrast between object and background",
            "Objects with clear boundaries",
            "Minimal overlapping objects",
          ],
        };
      default:
        return { title: "", items: [] };
    }
  }

  function handleChange() {
    if (selectedModelId !== null) {
      const model = models.find((m) => m.id === selectedModelId) || null;
      onModelChange?.({ modelId: selectedModelId, model });
    }
  }
</script>

<div class="model-selector">
  <label for="model-selector">
    <span>Model: <span class="required">*</span></span>
    <select
      name="model-selector"
      bind:value={selectedModelId}
      onchange={handleChange}
      {disabled}
    >
      <option value="">Choose Model</option>
      {#each models as model}
        <option value={model.id}>
          {model.name} ({model.base_type})
        </option>
      {/each}
    </select>
  </label>
</div>

{#if showTaskInstructions && selectedModel && selectedModel.task_type}
  <div class="task-instructions">
    <div
      class="task-badge-header"
      role="button"
      tabindex="0"
      onclick={() => (isTipsCollapsed = !isTipsCollapsed)}
      onkeydown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          isTipsCollapsed = !isTipsCollapsed;
        }
      }}
    >
      {#if selectedModel.task_type === "detect"}
        <span class="task-badge detect">🎯 Detection Model</span>
      {:else if selectedModel.task_type === "classify"}
        <span class="task-badge classify">🏷️ Classification Model</span>
      {:else if selectedModel.task_type === "segment"}
        <span class="task-badge segment">✂️ Segmentation Model</span>
      {/if}
      <button
        class="collapse-toggle"
        type="button"
        aria-label="Toggle tips"
        aria-expanded={!isTipsCollapsed}
        onclick={(e) => {
          e.stopPropagation();
          isTipsCollapsed = !isTipsCollapsed;
        }}
      >
        {isTipsCollapsed ? "▼" : "▲"}
      </button>
    </div>

    {#if !isTipsCollapsed}
      <div class="tips-content">
        <p class="task-description">
          {getTaskInstructions(selectedModel.task_type)}
        </p>

        {#if getTaskFormatGuidance(selectedModel.task_type).items.length > 0}
          {@const guidance = getTaskFormatGuidance(selectedModel.task_type)}
          <div class="task-guidance">
            <strong>{guidance.title}</strong>
            <ul>
              {#each guidance.items as item}
                <li>{item}</li>
              {/each}
            </ul>
          </div>
        {/if}

        {#if taskWarning}
          {@render taskWarning(selectedModel)}
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .model-selector {
    margin-bottom: 1rem;
  }

  .model-selector label {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .model-selector label span {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text-secondary, #6c757d);
  }

  .required {
    color: var(--color-accent, #e1604c);
  }

  .model-selector select {
    padding: 0.5rem;
    border: 1px solid var(--color-border, #e1e4e8);
    border-radius: 4px;
    background-color: var(--color-white, #ffffff);
    color: var(--color-text-primary, #1d2f43);
    font-size: 0.875rem;
    cursor: pointer;
    transition: border-color var(--transition-fast, 150ms);
  }

  .model-selector select:hover:not(:disabled) {
    border-color: var(--color-accent, #e1604c);
  }

  .model-selector select:focus {
    outline: none;
    border-color: var(--color-accent, #e1604c);
    box-shadow: 0 0 0 3px rgba(225, 96, 76, 0.1);
  }

  .model-selector select:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    background-color: var(--color-bg-secondary, #f5f7fa);
  }

  .task-instructions {
    margin-top: 0.75rem;
    border: 1px solid var(--color-border, #e1e4e8);
    border-radius: 6px;
    overflow: hidden;
    background-color: var(--color-white, #ffffff);
  }

  .task-badge-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem;
    background-color: var(--color-bg-secondary, #f5f7fa);
    cursor: pointer;
    user-select: none;
    transition: background-color var(--transition-fast, 150ms);
  }

  .task-badge-header:hover {
    background-color: #e9ecef;
  }

  .task-badge {
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .task-badge.detect {
    background-color: #d4edda;
    color: #155724;
  }

  .task-badge.classify {
    background-color: #d1ecf1;
    color: #0c5460;
  }

  .task-badge.segment {
    background-color: #fff3cd;
    color: #856404;
  }

  .collapse-toggle {
    background: none;
    border: none;
    color: var(--color-text-secondary, #6c757d);
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    font-size: 0.875rem;
    transition: color var(--transition-fast, 150ms);
  }

  .collapse-toggle:hover {
    color: var(--color-navy, #1d2f43);
  }

  .tips-content {
    padding: 0.75rem;
    border-top: 1px solid var(--color-border, #e1e4e8);
  }

  .task-description {
    margin: 0 0 0.75rem 0;
    font-size: 0.875rem;
    line-height: 1.5;
    color: var(--color-text-primary, #1d2f43);
  }

  .task-guidance {
    margin-top: 0.75rem;
    padding: 0.75rem;
    background-color: var(--color-bg-secondary, #f5f7fa);
    border-radius: 4px;
  }

  .task-guidance strong {
    display: block;
    margin-bottom: 0.5rem;
    font-size: 0.8rem;
    color: var(--color-navy, #1d2f43);
  }

  .task-guidance ul {
    margin: 0;
    padding-left: 1.25rem;
    font-size: 0.8rem;
    color: var(--color-text-secondary, #6c757d);
  }

  .task-guidance li {
    margin-bottom: 0.25rem;
  }

  .task-guidance li:last-child {
    margin-bottom: 0;
  }
</style>
