<script lang="ts">
  // Svelte 5: Props using $props() rune
  let {
    sourceType = "webcam",
    viewMode,
    galleryCount = 0,
    isDetecting = false,
    isRecording = false,
    onModeChange = undefined,
  }: {
    sourceType?: "rtsp" | "webcam";
    viewMode: "live" | "gallery";
    galleryCount?: number;
    isDetecting?: boolean;
    isRecording?: boolean;
    onModeChange?: ((detail: { mode: "live" | "gallery" }) => void) | undefined;
  } = $props();

  function handleModeChange(mode: "live" | "gallery") {
    console.log("Switching view mode to:", mode);
    onModeChange?.({ mode });
  }
</script>

<div class="webcam-mode-switcher">
  <div class="segmented-control">
    <button
      class="segment-button"
      class:active={viewMode === "live"}
      on:click={() => handleModeChange("live")}
      disabled={isDetecting}
      type="button"
    >
      <span class="segment-icon">🔴</span>
      <span class="segment-label">Live</span>
      {#if isRecording && viewMode !== "live"}
        <span class="rec-badge">REC</span>
      {/if}
    </button>
    <button
      class="segment-button"
      class:active={viewMode === "gallery"}
      on:click={() => handleModeChange("gallery")}
      disabled={galleryCount === 0 || isDetecting}
      type="button"
    >
      <span class="segment-icon">📸</span>
      <span class="segment-label">History</span>
      {#if galleryCount > 0}
        <span class="count-badge">{galleryCount}</span>
      {/if}
    </button>
  </div>
</div>

<style>
  .webcam-mode-switcher {
    display: flex;
    justify-content: center;
    padding: 0.5rem 0;
  }

  .segmented-control {
    display: inline-flex;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 4px;
    gap: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    backdrop-filter: blur(10px);
  }

  .segment-button {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.6);
    font-size: 0.95rem;
    font-weight: 500;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
    min-width: 120px;
    justify-content: center;
  }

  .segment-button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .segment-button:not(:disabled):hover {
    color: rgba(255, 255, 255, 0.8);
  }

  .segment-button.active {
    background: rgba(255, 255, 255, 0.95);
    color: var(--color-navy, #1d2f43);
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
  }

  .segment-icon {
    font-size: 1.1rem;
    line-height: 1;
  }

  .segment-label {
    font-weight: 600;
  }

  .count-badge {
    position: absolute;
    top: 4px;
    right: 4px;
    background: var(--color-accent, #e1604c);
    color: white;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 8px;
    min-width: 20px;
    text-align: center;
  }

  .rec-badge {
    position: absolute;
    top: 6px;
    right: 6px;
    background: #ff3b30;
    color: white;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 8px;
    letter-spacing: 0.5px;
    animation: pulse 2s ease-in-out infinite;
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.6;
    }
  }
</style>
