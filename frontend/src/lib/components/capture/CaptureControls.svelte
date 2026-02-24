<script lang="ts">
  /**
   * CaptureControls - Unified start/stop/capture buttons for capture page
   * Adapts button layout and labels based on source type and capture mode
   */

  // Svelte 5: Props using $props() rune
  let {
    sourceType = "image",
    captureMode = "manual",
    isDetecting = false,
    disabled = false,
    hasFile = false,
    hasUrl = false,
    onStart = undefined,
    onStop = undefined,
    onCapture = undefined,
    onReset = undefined,
  }: {
    sourceType?: "image" | "batch" | "video" | "webcam" | "rtsp";
    captureMode?: "manual" | "continuous";
    isDetecting?: boolean;
    disabled?: boolean;
    hasFile?: boolean;
    hasUrl?: boolean;
    onStart?: (() => void) | undefined;
    onStop?: (() => void) | undefined;
    onCapture?: (() => void) | undefined;
    onReset?: (() => void) | undefined;
  } = $props();

  // Button handlers
  function handleStart() {
    if (disabled) return;
    onStart?.();
  }

  function handleStop() {
    onStop?.();
  }

  function handleCapture() {
    if (disabled) return;
    onCapture?.();
  }

  function handleReset() {
    if (disabled || isDetecting) return;
    onReset?.();
  }

  // Svelte 5: Derived reactive values
  const canStart = $derived(
    !disabled &&
      !isDetecting &&
      (sourceType === "image"
        ? hasFile
        : sourceType === "batch"
          ? hasFile
          : sourceType === "video"
            ? hasFile
            : sourceType === "webcam"
              ? true
              : sourceType === "rtsp"
                ? hasUrl
                : false),
  );

  const showCaptureButton = $derived(
    isDetecting &&
      captureMode === "manual" &&
      (sourceType === "webcam" ||
        sourceType === "rtsp" ||
        sourceType === "video"),
  );

  const startButtonLabel = $derived(
    sourceType === "image"
      ? "Start"
      : sourceType === "batch"
        ? "Process Batch"
        : sourceType === "video"
          ? captureMode === "manual"
            ? "Start Video Session"
            : "Start Detection"
          : sourceType === "webcam"
            ? captureMode === "manual"
              ? "Start Session"
              : "Start Detection"
            : sourceType === "rtsp"
              ? captureMode === "manual"
                ? "Connect & Start"
                : "Start Stream"
              : "Start",
  );

  const captureButtonLabel = $derived(
    sourceType === "video"
      ? "📸 Capture Frame"
      : sourceType === "webcam"
        ? "📸 Capture"
        : sourceType === "rtsp"
          ? "📸 Capture Frame"
          : "📸 Capture",
  );
</script>

<div class="capture-controls">
  {#if !isDetecting}
    <!-- Start Button -->
    <button
      class="btn btn-primary btn-start"
      onclick={handleStart}
      disabled={!canStart}
    >
      <span class="btn-icon">▶️</span>
      <span class="btn-label">{startButtonLabel}</span>
    </button>

    <!-- Reset Button -->
    <button
      class="btn btn-outline btn-reset"
      onclick={handleReset}
      disabled={disabled || isDetecting}
    >
      <span class="btn-icon">🔄</span>
      <span class="btn-label">Reset</span>
    </button>
  {:else}
    <!-- Stop Button -->
    <button class="btn btn-danger btn-stop" onclick={handleStop}>
      <span class="btn-icon">⏹️</span>
      <span class="btn-label">Stop</span>
    </button>

    <!-- Capture Button (Manual Mode Only) -->
    {#if showCaptureButton}
      <button
        class="btn btn-accent btn-capture"
        onclick={handleCapture}
        {disabled}
      >
        <span class="btn-label">{captureButtonLabel}</span>
      </button>
    {/if}
  {/if}
</div>

<style>
  .capture-controls {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
  }

  /* Base Button Styles */
  .btn {
    display: inline-flex;
    margin-top: 0.7rem;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.875rem 1.5rem;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
    font-size: 1rem;
    transition: all 0.2s ease;
    min-width: 280px;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none !important;
  }

  .btn-icon {
    font-size: 1.1rem;
  }

  .btn-label {
    white-space: nowrap;
  }

  /* Start Button (Primary) */
  .btn-primary {
    background: var(--color-accent, #e1604c);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--color-accent, #e1604c);
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(225, 96, 76, 0.25);
  }

  .btn-primary:active:not(:disabled) {
    transform: translateY(0);
  }

  /* Stop Button (Danger) */
  .btn-danger {
    background: #dc3545;
    color: white;
  }

  .btn-danger:hover:not(:disabled) {
    background: #c82333;
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(220, 53, 69, 0.25);
  }

  .btn-danger:active:not(:disabled) {
    transform: translateY(0);
  }

  /* Capture Button (Accent) */
  .btn-accent {
    background: var(--color-accent, #e1604c);
    color: white;
  }

  .btn-accent:hover:not(:disabled) {
    background: #d14533;
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(225, 96, 76, 0.25);
  }

  .btn-accent:active:not(:disabled) {
    transform: translateY(0);
  }

  /* Reset Button (Outline Style) */
  .btn-outline {
    background: var(--color-bg-primary);
    color: var(--color-accent);
    border: 2px solid rgba(255, 255, 255, 0.3);
  }

  .btn-outline:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.5);
    transform: translateY(-2px);
  }

  .btn-outline:active:not(:disabled) {
    transform: translateY(0);
  }

  /* Responsive adjustments */
  @media (max-width: 768px) {
    .capture-controls {
      width: 100%;
    }

    .btn {
      flex: 1;
      min-width: auto;
    }
  }
</style>
