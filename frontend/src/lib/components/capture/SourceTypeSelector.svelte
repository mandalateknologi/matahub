<script lang="ts">
  /**
   * SourceTypeSelector - Component for selecting inference source type
   *
   * Extracted from capture page (Phase 1) to reduce complexity and improve reusability.
   * Provides a simple dropdown for switching between different inference sources.
   */

  type SourceType = "image" | "batch" | "video" | "webcam" | "rtsp";

  // Svelte 5: Props using $props() rune
  let {
    sourceType = $bindable("image" as SourceType),
    disabled = false,
  }: {
    sourceType?: SourceType;
    disabled?: boolean;
  } = $props();
</script>

<div class="source-selector">
  <label for="sourceType">
    <span>Source Type: *</span>
    <select name="sourceType" bind:value={sourceType} {disabled}>
      <option value="image">Single Image</option>
      <option value="batch">Batch Images</option>
      <option value="video">Video File</option>
      <option value="webcam">Camera (Web)</option>
      <option value="rtsp">RTSP Stream</option>
    </select>
  </label>
</div>

<style>
  .source-selector {
    margin-bottom: 1rem;
    margin-top: 0.5rem;
  }

  .source-selector label {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .source-selector label span {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text-secondary, #6c757d);
  }

  .source-selector select {
    padding: 0.5rem;
    border: 1px solid var(--color-border, #e1e4e8);
    border-radius: 4px;
    background-color: var(--color-white, #ffffff);
    color: var(--color-text-primary, #1d2f43);
    font-size: 0.875rem;
    cursor: pointer;
    transition: border-color var(--transition-fast, 150ms);
  }

  .source-selector select:hover:not(:disabled) {
    border-color: var(--color-accent, #e1604c);
  }

  .source-selector select:focus {
    outline: none;
    border-color: var(--color-accent, #e1604c);
    box-shadow: 0 0 0 3px rgba(225, 96, 76, 0.1);
  }

  .source-selector select:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    background-color: var(--color-bg-secondary, #f5f7fa);
  }
</style>
