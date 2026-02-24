<script lang="ts">
  import { onDestroy } from "svelte";
  import { InferenceAPI } from "../../api/inference";

  export let jobId: number;
  export let exportJobId: number;
  export let exportType: string;
  export let onClose: () => void;

  let progress = 0;
  let status = "processing";
  let error = "";
  let pollInterval: number | null = null;

  // Start polling for export status
  pollInterval = window.setInterval(async () => {
    try {
      const exportJob = await InferenceAPI.getExportStatus(jobId, exportJobId);
      progress = exportJob.progress || 0;
      status = exportJob.status;

      if (status === "completed") {
        clearInterval(pollInterval!);
        pollInterval = null;
        // Trigger download
        await InferenceAPI.downloadExport(jobId, exportJobId);
        // Close modal after a brief delay
        setTimeout(onClose, 1000);
      } else if (status === "failed") {
        clearInterval(pollInterval!);
        pollInterval = null;
        error = exportJob.error_message || "Export failed";
      }
    } catch (err: any) {
      console.error("Error polling export status:", err);
      error = err.response?.data?.detail || "Failed to check export status";
      clearInterval(pollInterval!);
      pollInterval = null;
    }
  }, 2000);

  onDestroy(() => {
    if (pollInterval) {
      clearInterval(pollInterval);
    }
  });

  function handleCancel() {
    if (pollInterval) {
      clearInterval(pollInterval);
    }
    onClose();
  }

  function getExportTypeLabel(type: string): string {
    const labels: Record<string, string> = {
      images_zip: "Images (ZIP)",
      data_json: "Data (JSON)",
      data_csv: "Data (CSV)",
      report_pdf: "PDF Report",
    };
    return labels[type] || type;
  }
</script>

<div class="modal-overlay" on:click={handleCancel}>
  <div class="modal" on:click|stopPropagation>
    <div class="modal-header">
      <h2>Exporting {getExportTypeLabel(exportType)}</h2>
    </div>

    <div class="modal-body">
      {#if error}
        <div class="error-message">
          <span class="error-icon">❌</span>
          <p>{error}</p>
        </div>
      {:else if status === "completed"}
        <div class="success-message">
          <span class="success-icon">✅</span>
          <p>Export completed! Download should start automatically...</p>
        </div>
      {:else}
        <div class="progress-container">
          <div class="progress-label">
            {#if status === "pending"}
              <span>⏳ Preparing export...</span>
            {:else if status === "processing"}
              <span>🔄 Processing ({Math.round(progress)}%)</span>
            {/if}
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width: {progress}%"></div>
          </div>
        </div>
      {/if}
    </div>

    <div class="modal-footer">
      {#if status !== "completed"}
        <button class="btn btn-outline" on:click={handleCancel}>
          {error ? "Close" : "Cancel"}
        </button>
      {/if}
    </div>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal {
    background: var(--color-white);
    border-radius: 12px;
    box-shadow: var(--shadow-lg);
    width: 90%;
    max-width: 500px;
    max-height: 90vh;
    overflow-y: auto;
  }

  .modal-header {
    padding: var(--spacing-lg);
    border-bottom: 1px solid var(--color-border);
  }

  .modal-header h2 {
    margin: 0;
    font-size: var(--font-size-xl);
    color: var(--color-navy);
  }

  .modal-body {
    padding: var(--spacing-xl);
  }

  .progress-container {
    margin: var(--spacing-md) 0;
  }

  .progress-label {
    margin-bottom: var(--spacing-sm);
    font-size: var(--font-size-base);
    color: var(--color-navy);
    font-weight: 500;
  }

  .progress-bar {
    width: 100%;
    height: 24px;
    background: var(--color-bg-light1);
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--color-border);
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #3b82f6, #60a5fa);
    transition: width 0.3s ease;
    border-radius: 12px;
  }

  .error-message,
  .success-message {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    padding: var(--spacing-md);
    border-radius: 8px;
  }

  .error-message {
    background: #fee;
    border: 1px solid #f88;
    color: #c00;
  }

  .success-message {
    background: #efe;
    border: 1px solid #8f8;
    color: #060;
  }

  .error-icon,
  .success-icon {
    font-size: var(--font-size-2xl);
  }

  .modal-footer {
    padding: var(--spacing-lg);
    border-top: 1px solid var(--color-border);
    display: flex;
    justify-content: flex-end;
    gap: var(--spacing-md);
  }
</style>
