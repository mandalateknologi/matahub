<script lang="ts">
  /**
   * SmartSettingsPanel - Confidence and class filter controls
   *
   * Extracted from capture page (Phase 1) to improve code organization.
   * Handles confidence slider and class filter tag input.
   *
   * Supports both legacy bind: mode and Phase 3 store callback mode.
   */

  // Svelte 5: Props using $props() rune
  let {
    confidence = $bindable(0.5),
    classFilter = $bindable([]),
    disabled = false,
    skipFrames = $bindable(5),
    showSkipFrames = false,
    // Phase 3: Optional callbacks for store mode
    onConfidenceChange = undefined,
    onClassFilterChange = undefined,
    onSkipFramesChange = undefined,
  }: {
    confidence?: number;
    classFilter?: string[];
    disabled?: boolean;
    skipFrames?: number;
    showSkipFrames?: boolean;
    // Callbacks for Phase 3 store integration
    onConfidenceChange?: ((value: number) => void) | undefined;
    onClassFilterChange?: ((value: string[]) => void) | undefined;
    onSkipFramesChange?: ((value: number) => void) | undefined;
  } = $props();

  let newClassTag = "";

  function addTag() {
    const trimmed = newClassTag.trim();
    if (trimmed && !classFilter.includes(trimmed)) {
      const newFilter = [...classFilter, trimmed];
      if (onClassFilterChange) {
        onClassFilterChange(newFilter);
      } else {
        classFilter = newFilter;
      }
      newClassTag = "";
    }
  }

  function removeTag(tag: string) {
    console.log("[SmartSettingsPanel] Removing tag:", tag);
    const newFilter = classFilter.filter((t) => t !== tag);
    console.log(
      "[SmartSettingsPanel] New filter:",
      newFilter,
      "Has callback:",
      !!onClassFilterChange,
    );
    if (onClassFilterChange) {
      onClassFilterChange(newFilter);
    } else {
      classFilter = newFilter;
    }
  }

  function handleTagKeydown(e: KeyboardEvent) {
    if (e.key === "Enter" && newClassTag.trim()) {
      e.preventDefault();
      addTag();
    }
  }

  function handleConfidenceChange(e: Event) {
    const value = +(e.target as HTMLInputElement).value;
    if (onConfidenceChange) {
      onConfidenceChange(value);
    } else {
      confidence = value;
    }
  }

  function handleSkipFramesChange(e: Event) {
    const value = +(e.target as HTMLInputElement).value;
    if (onSkipFramesChange) {
      onSkipFramesChange(value);
    } else {
      skipFrames = value;
    }
  }
</script>

<section class="smart-settings-panel">
  <h3>Smart Settings</h3>

  <div class="confidence-control">
    <label>
      <span>Confidence: {confidence.toFixed(2)}</span>
      <input
        type="range"
        min="0"
        max="1"
        step="0.05"
        value={confidence}
        on:input={handleConfidenceChange}
        {disabled}
      />
    </label>
    <p class="help-text">Lower = more detections</p>
  </div>

  {#if showSkipFrames}
    <div class="skip-frames-control">
      <label>
        <span>Skip Frames: {skipFrames}</span>
        <input
          type="range"
          min="1"
          max="30"
          step="1"
          value={skipFrames}
          on:input={handleSkipFramesChange}
          {disabled}
        />
      </label>
      <p class="help-text">
        Process every Nth frame (higher = faster, less accurate)
      </p>
    </div>
  {/if}

  <div class="class-filter-control">
    <div class="section-header">
      <span>Class Filter (optional)</span>
    </div>
    <div class="tags-input-container">
      <div class="tags-list">
        {#each classFilter as tag}
          <span class="tag">
            {tag}
            <button
              type="button"
              class="tag-remove"
              {disabled}
              on:click={() => removeTag(tag)}
            >
              ×
            </button>
          </span>
        {/each}
        <input
          type="text"
          class="tag-input"
          placeholder="Add a class..."
          {disabled}
          bind:value={newClassTag}
          on:keydown={handleTagKeydown}
        />
      </div>
    </div>
    <p class="help-text">
      Only predict specific classes. Press Enter to add (leave empty for all)
    </p>
  </div>
</section>

<style>
  .smart-settings-panel {
    padding: 1rem;
    background-color: var(--color-bg-secondary, #f5f7fa);
    border-radius: 8px;
    margin-bottom: 1rem;
  }

  .smart-settings-panel h3 {
    margin: 0 0 1rem 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--color-navy, #1d2f43);
  }

  .confidence-control,
  .skip-frames-control {
    margin-bottom: 1rem;
  }

  .confidence-control label,
  .skip-frames-control label {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .confidence-control label span,
  .skip-frames-control label span {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text-secondary, #6c757d);
  }

  input[type="range"] {
    width: 100%;
    height: 6px;
    border-radius: 3px;
    background: var(--color-border, #e1e4e8);
    outline: none;
    -webkit-appearance: none;
  }

  input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--color-accent, #e1604c);
    cursor: pointer;
    transition: transform var(--transition-fast, 150ms);
  }

  input[type="range"]::-webkit-slider-thumb:hover {
    transform: scale(1.1);
  }

  input[type="range"]::-moz-range-thumb {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--color-accent, #e1604c);
    cursor: pointer;
    border: none;
    transition: transform var(--transition-fast, 150ms);
  }

  input[type="range"]::-moz-range-thumb:hover {
    transform: scale(1.1);
  }

  input[type="range"]:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  input[type="range"]:disabled::-webkit-slider-thumb {
    cursor: not-allowed;
  }

  input[type="range"]:disabled::-moz-range-thumb {
    cursor: not-allowed;
  }

  .help-text {
    margin: 0.25rem 0 0 0;
    font-size: 0.75rem;
    color: var(--color-text-tertiary, #adb5bd);
    font-style: italic;
  }

  .class-filter-control {
    margin-top: 1rem;
  }

  .section-header {
    margin-bottom: 0.5rem;
  }

  .section-header span {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text-secondary, #6c757d);
  }

  .tags-input-container {
    border: 1px solid var(--color-border, #e1e4e8);
    border-radius: 4px;
    background-color: var(--color-white, #ffffff);
    padding: 0.5rem;
    min-height: 42px;
  }

  .tags-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
  }

  .tag {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    background-color: var(--color-accent, #e1604c);
    color: white;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .tag-remove {
    background: none;
    border: none;
    color: white;
    cursor: pointer;
    padding: 0;
    font-size: 1rem;
    line-height: 1;
    opacity: 0.8;
    transition: opacity var(--transition-fast, 150ms);
  }

  .tag-remove:hover:not(:disabled) {
    opacity: 1;
  }

  .tag-remove:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  .tag-input {
    flex: 1;
    min-width: 120px;
    border: none;
    outline: none;
    padding: 0.25rem;
    font-size: 0.875rem;
    color: var(--color-text-primary, #1d2f43);
  }

  .tag-input::placeholder {
    color: var(--color-text-tertiary, #adb5bd);
  }

  .tag-input:disabled {
    background-color: transparent;
    cursor: not-allowed;
  }
</style>
