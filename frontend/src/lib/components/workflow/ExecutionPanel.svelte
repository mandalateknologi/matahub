<script lang="ts">
  import type { WorkflowExecutionDetail } from "../../api/workflows";
  import { onMount, onDestroy } from "svelte";

  // Props
  let {
    execution = $bindable(),
    onClose,
    onViewDetails,
    onCancel,
    onSwitchExecution,
    activeExecutions = [],
  }: {
    execution: WorkflowExecutionDetail;
    onClose: () => void;
    onViewDetails: () => void;
    onCancel: () => void;
    onSwitchExecution?: (executionId: number) => void;
    activeExecutions?: WorkflowExecutionDetail[];
  } = $props();

  // State
  let errorExpanded = $state(false);
  let stepDetailsExpanded = $state(false);
  let elapsedSeconds = $state(0);
  let elapsedInterval: number | null = null;
  let showExecutionDropdown = $state(false);

  // Derived state
  const status = $derived(execution.execution.status);
  const progress = $derived(execution.execution.progress);
  const errorMessage = $derived(execution.execution.error_message);
  const currentStep = $derived(
    execution.steps.find((s) => s.status === "running")
  );
  const failedSteps = $derived(
    execution.steps.filter((s) => s.status === "failed")
  );
  const completedSteps = $derived(
    execution.steps.filter((s) => s.status === "completed")
  );
  const hasMultipleExecutions = $derived(activeExecutions.length > 1);

  // Calculate elapsed time
  $effect(() => {
    if (execution.execution.started_at) {
      const startTime = new Date(execution.execution.started_at).getTime();

      // Clear existing interval
      if (elapsedInterval) {
        clearInterval(elapsedInterval);
      }

      // Update elapsed time every second
      const updateElapsed = () => {
        const now = Date.now();
        elapsedSeconds = Math.floor((now - startTime) / 1000);
      };

      updateElapsed();
      elapsedInterval = setInterval(updateElapsed, 1000);
    }
  });

  onDestroy(() => {
    if (elapsedInterval) {
      clearInterval(elapsedInterval);
    }
  });

  function formatElapsedTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins > 0) {
      return `${mins}m ${secs}s`;
    }
    return `${secs}s`;
  }

  function getNodeIcon(nodeType: string): string {
    const icons: Record<string, string> = {
      trigger: "⚡",
      chat_trigger: "💬",
      schedule_trigger: "⏰",
      data_input: "📥",
      session_input: "📋",
      train_model: "🏋️",
      detect_image: "🔍",
      detect_batch: "📦",
      export_results: "📤",
      data_output: "📊",
      save_to_database: "💾",
      send_email: "📧",
      send_notification: "🔔",
    };
    return icons[nodeType] || "⚙️";
  }

  function getStatusBadgeClass(status: string): string {
    const classes: Record<string, string> = {
      pending: "badge-gray",
      running: "badge-blue",
      completed: "badge-success",
      failed: "badge-danger",
      skipped: "badge-gray",
      cancelled: "badge-warning",
    };
    return classes[status] || "badge-gray";
  }

  function downloadLogs() {
    const logs = {
      workflow_name: execution.workflow_name,
      execution_id: execution.execution.id,
      status: execution.execution.status,
      started_at: execution.execution.started_at,
      completed_at: execution.execution.completed_at,
      duration_seconds: elapsedSeconds,
      progress: execution.execution.progress,
      error_message: execution.execution.error_message,
      steps: execution.steps.map((step) => ({
        node_id: step.node_id,
        node_type: step.node_type,
        status: step.status,
        started_at: step.started_at,
        completed_at: step.completed_at,
        input_data: step.input_data,
        output_data: step.output_data,
        error_message: step.error_message,
        training_job_id: step.training_job_id,
        detection_job_id: step.detection_job_id,
        export_job_id: step.export_job_id,
      })),
    };

    const blob = new Blob([JSON.stringify(logs, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `workflow-execution-${execution.execution.id}-${new Date().toISOString()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function requestNotificationPermission() {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  }

  // Request notification permission on mount
  onMount(() => {
    requestNotificationPermission();
  });

  // Show notification when execution completes
  $effect(() => {
    if (
      status === "completed" ||
      status === "failed" ||
      status === "cancelled"
    ) {
      if ("Notification" in window && Notification.permission === "granted") {
        const title =
          status === "completed"
            ? "✅ Workflow Completed"
            : status === "failed"
              ? "❌ Workflow Failed"
              : "⚠️ Workflow Cancelled";
        const body = `${execution.workflow_name} - ${progress}% complete`;

        new Notification(title, {
          body,
          icon: "/favicon.ico",
          badge: "/favicon.ico",
        });
      }

      // Play sound
      try {
        const audio = new Audio(
          status === "completed" ? "/sounds/success.mp3" : "/sounds/error.mp3"
        );
        audio.volume = 0.3;
        audio.play().catch(() => {
          /* Ignore audio errors */
        });
      } catch (e) {
        /* Ignore if audio files don't exist */
      }
    }
  });
</script>

<div
  class="execution-panel"
  class:error={status === "failed"}
  class:success={status === "completed"}
  class:cancelled={status === "cancelled"}
>
  <div class="panel-content">
    <!-- Status Section -->
    <div class="status-section">
      <div class="status-header">
        <span class="status-badge {getStatusBadgeClass(status)}">
          {#if status === "running"}
            <span class="spinner-inline">⟳</span>
          {/if}
          {status.toUpperCase()}
        </span>

        {#if hasMultipleExecutions && onSwitchExecution}
          <div class="execution-dropdown">
            <button
              class="dropdown-toggle"
              onclick={() => (showExecutionDropdown = !showExecutionDropdown)}
            >
              Execution #{execution.execution.id} ▼
            </button>
            {#if showExecutionDropdown}
              <div class="dropdown-menu">
                {#each activeExecutions as exec}
                  <button
                    class="dropdown-item"
                    class:active={exec.execution.id === execution.execution.id}
                    onclick={() => {
                      onSwitchExecution(exec.execution.id);
                      showExecutionDropdown = false;
                    }}
                  >
                    <span
                      class="status-dot {getStatusBadgeClass(
                        exec.execution.status
                      )}"
                    ></span>
                    Execution #{exec.execution.id} ({exec.execution.status})
                  </button>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      </div>

      {#if currentStep}
        <div class="current-step">
          <span class="step-icon">{getNodeIcon(currentStep.node_type)}</span>
          <span class="step-label">{currentStep.node_type}</span>
        </div>
      {:else if status === "completed"}
        <div class="current-step success">
          <span class="step-icon">✓</span>
          <span class="step-label">Completed {completedSteps.length} steps</span
          >
        </div>
      {:else if status === "failed"}
        <div class="current-step error">
          <span class="step-icon">✗</span>
          <span class="step-label">Failed at step {failedSteps.length}</span>
        </div>
      {/if}
    </div>

    <!-- Progress Section -->
    <div class="progress-section">
      <div class="progress-info">
        <div class="progress-bar">
          <div
            class="progress-fill"
            class:running={status === "running"}
            class:success={status === "completed"}
            class:error={status === "failed"}
            style="width: {progress}%"
          ></div>
        </div>
        <span class="progress-text">{progress}%</span>
      </div>
      <div class="elapsed-time">
        <span class="time-icon">⏱️</span>
        <span>{formatElapsedTime(elapsedSeconds)}</span>
      </div>
    </div>

    <!-- Actions Section -->
    <div class="actions">
      {#if status === "running"}
        <button class="btn-action btn-stop" onclick={onCancel}>
          <span class="btn-icon">⏹️</span>
          Stop
        </button>
      {/if}

      <button class="btn-action btn-download" onclick={downloadLogs}>
        <span class="btn-icon">💾</span>
        Download Logs
      </button>

      <button class="btn-action btn-link" onclick={onViewDetails}>
        View Details →
      </button>

      <button class="btn-close" onclick={onClose}>×</button>
    </div>
  </div>

  <!-- Error Details (Expandable) -->
  {#if status === "failed" && (errorMessage || failedSteps.length > 0)}
    <div class="error-details">
      <button
        class="error-header"
        onclick={() => (errorExpanded = !errorExpanded)}
      >
        <span class="error-icon">⚠️</span>
        <strong>Error Details</strong>
        <span class="expand-icon">{errorExpanded ? "▼" : "▶"}</span>
      </button>

      {#if errorExpanded}
        <div class="error-content">
          {#if errorMessage}
            <div class="error-message">
              <strong>Workflow Error:</strong>
              {errorMessage}
            </div>
          {/if}

          {#if failedSteps.length > 0}
            <div class="failed-steps">
              <strong>Failed Steps:</strong>
              {#each failedSteps as step}
                <div class="step-error">
                  <div class="step-error-header">
                    <span class="step-icon">{getNodeIcon(step.node_type)}</span>
                    <span>{step.node_type}</span>
                    <span class="step-id">({step.node_id})</span>
                  </div>
                  {#if step.error_message}
                    <div class="step-error-message">{step.error_message}</div>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}

  <!-- Step Details (Expandable) -->
  {#if completedSteps.length > 0}
    <div class="step-details">
      <button
        class="step-details-header"
        onclick={() => (stepDetailsExpanded = !stepDetailsExpanded)}
      >
        <span class="step-icon">📋</span>
        <strong>Step Details ({completedSteps.length} completed)</strong>
        <span class="expand-icon">{stepDetailsExpanded ? "▼" : "▶"}</span>
      </button>

      {#if stepDetailsExpanded}
        <div class="step-details-content">
          {#each completedSteps as step}
            <div class="step-detail-item">
              <div class="step-detail-header">
                <span class="step-icon">{getNodeIcon(step.node_type)}</span>
                <strong>{step.node_type}</strong>
                <span class="step-id">({step.node_id})</span>
                <span class="badge {getStatusBadgeClass(step.status)}"
                  >{step.status}</span
                >
              </div>

              {#if step.input_data && Object.keys(step.input_data).length > 0}
                <div class="step-data">
                  <strong>Input:</strong>
                  <pre><code>{JSON.stringify(step.input_data, null, 2)}</code
                    ></pre>
                </div>
              {/if}

              {#if step.output_data && Object.keys(step.output_data).length > 0}
                <div class="step-data">
                  <strong>Output:</strong>
                  <pre><code>{JSON.stringify(step.output_data, null, 2)}</code
                    ></pre>
                </div>
              {/if}

              {#if step.training_job_id}
                <div class="step-job-link">
                  <strong>Training Job:</strong>
                  <a href="#/training/{step.training_job_id}">
                    #{step.training_job_id}
                  </a>
                </div>
              {/if}

              {#if step.detection_job_id}
                <div class="step-job-link">
                  <strong>Detection Job:</strong>
                  <a href="#/detection/jobs/{step.detection_job_id}">
                    #{step.detection_job_id}
                  </a>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .execution-panel {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    border-top: 3px solid #3b82f6;
    box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.1);
    z-index: 1000;
    animation: slideUp 0.3s ease;
    max-height: 80vh;
    overflow-y: auto;
  }

  .execution-panel.error {
    border-top-color: #ef4444;
    background: linear-gradient(to bottom, #fef2f2 0%, #ffffff 100%);
  }

  .execution-panel.success {
    border-top-color: #10b981;
    background: linear-gradient(to bottom, #f0fdf4 0%, #ffffff 100%);
  }

  .execution-panel.cancelled {
    border-top-color: #f59e0b;
    background: linear-gradient(to bottom, #fffbeb 0%, #ffffff 100%);
  }

  @keyframes slideUp {
    from {
      transform: translateY(100%);
    }
    to {
      transform: translateY(0);
    }
  }

  .panel-content {
    display: flex;
    align-items: center;
    gap: 2rem;
    padding: 1rem 2rem;
  }

  .status-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    min-width: 200px;
  }

  .status-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.75rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .badge-gray {
    background: #e5e7eb;
    color: #374151;
  }

  .badge-blue {
    background: #dbeafe;
    color: #1e40af;
  }

  .badge-success {
    background: #d1fae5;
    color: #065f46;
  }

  .badge-danger {
    background: #fee2e2;
    color: #991b1b;
  }

  .badge-warning {
    background: #fef3c7;
    color: #92400e;
  }

  .spinner-inline {
    display: inline-block;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .execution-dropdown {
    position: relative;
  }

  .dropdown-toggle {
    padding: 0.25rem 0.5rem;
    background: transparent;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .dropdown-toggle:hover {
    background: #f3f4f6;
  }

  .dropdown-menu {
    position: absolute;
    top: 100%;
    left: 0;
    margin-top: 0.25rem;
    background: white;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    min-width: 200px;
    z-index: 10;
  }

  .dropdown-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.5rem 0.75rem;
    background: transparent;
    border: none;
    text-align: left;
    font-size: 0.875rem;
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .dropdown-item:hover {
    background: #f3f4f6;
  }

  .dropdown-item.active {
    background: #dbeafe;
    font-weight: 600;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .current-step {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    color: #6b7280;
  }

  .current-step.success {
    color: #059669;
  }

  .current-step.error {
    color: #dc2626;
  }

  .step-icon {
    font-size: 1rem;
  }

  .step-label {
    font-weight: 500;
  }

  .progress-section {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .progress-info {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .progress-bar {
    flex: 1;
    height: 8px;
    background: #e5e7eb;
    border-radius: 4px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    transition: width 0.5s ease;
  }

  .progress-fill.running {
    background: linear-gradient(90deg, #3b82f6, #60a5fa);
    animation: shimmer 2s ease-in-out infinite;
  }

  .progress-fill.success {
    background: linear-gradient(90deg, #10b981, #34d399);
  }

  .progress-fill.error {
    background: linear-gradient(90deg, #ef4444, #f87171);
  }

  @keyframes shimmer {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.7;
    }
  }

  .progress-text {
    font-size: 0.875rem;
    font-weight: 600;
    color: #374151;
    min-width: 45px;
    text-align: right;
  }

  .elapsed-time {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.875rem;
    color: #6b7280;
    white-space: nowrap;
  }

  .time-icon {
    font-size: 1rem;
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .btn-action {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.5rem 0.75rem;
    background: transparent;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
  }

  .btn-action:hover {
    background: #f3f4f6;
  }

  .btn-stop {
    border-color: #ef4444;
    color: #ef4444;
  }

  .btn-stop:hover {
    background: #fef2f2;
  }

  .btn-download {
    border-color: #3b82f6;
    color: #3b82f6;
  }

  .btn-download:hover {
    background: #eff6ff;
  }

  .btn-link {
    color: #3b82f6;
    border-color: transparent;
  }

  .btn-link:hover {
    background: #eff6ff;
  }

  .btn-icon {
    font-size: 1rem;
  }

  .btn-close {
    padding: 0.25rem 0.5rem;
    background: transparent;
    border: none;
    font-size: 1.5rem;
    color: #6b7280;
    cursor: pointer;
    line-height: 1;
    transition: color 0.15s ease;
  }

  .btn-close:hover {
    color: #ef4444;
  }

  /* Error Details */
  .error-details {
    border-top: 1px solid #fee2e2;
    background: #fef2f2;
  }

  .error-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.75rem 2rem;
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .error-header:hover {
    background: #fee2e2;
  }

  .error-icon {
    font-size: 1.25rem;
  }

  .expand-icon {
    margin-left: auto;
    font-size: 0.75rem;
    color: #6b7280;
  }

  .error-content {
    padding: 0 2rem 1rem 2rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .error-message {
    padding: 0.75rem;
    background: white;
    border-left: 3px solid #ef4444;
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .failed-steps {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .step-error {
    padding: 0.75rem;
    background: white;
    border-left: 3px solid #f59e0b;
    border-radius: 4px;
  }

  .step-error-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    font-weight: 600;
  }

  .step-id {
    font-size: 0.75rem;
    color: #6b7280;
    font-weight: normal;
  }

  .step-error-message {
    font-size: 0.875rem;
    color: #dc2626;
  }

  /* Step Details */
  .step-details {
    border-top: 1px solid #e5e7eb;
  }

  .step-details-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.75rem 2rem;
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .step-details-header:hover {
    background: #f9fafb;
  }

  .step-details-content {
    padding: 0 2rem 1rem 2rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    max-height: 300px;
    overflow-y: auto;
  }

  .step-detail-item {
    padding: 0.75rem;
    background: #f9fafb;
    border-left: 3px solid #10b981;
    border-radius: 4px;
  }

  .step-detail-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .step-data {
    margin-top: 0.5rem;
  }

  .step-data strong {
    display: block;
    margin-bottom: 0.25rem;
    font-size: 0.75rem;
    color: #6b7280;
  }

  .step-data pre {
    margin: 0;
    padding: 0.5rem;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
    font-size: 0.75rem;
    overflow-x: auto;
  }

  .step-data code {
    font-family: "Monaco", "Menlo", "Ubuntu Mono", monospace;
    color: #374151;
  }

  .step-job-link {
    margin-top: 0.5rem;
    font-size: 0.875rem;
  }

  .step-job-link strong {
    color: #6b7280;
  }

  .step-job-link a {
    color: #3b82f6;
    text-decoration: none;
  }

  .step-job-link a:hover {
    text-decoration: underline;
  }

  /* Responsive */
  @media (max-width: 1024px) {
    .panel-content {
      flex-wrap: wrap;
      gap: 1rem;
    }

    .status-section {
      min-width: auto;
    }

    .progress-section {
      flex: 1 1 100%;
    }

    .actions {
      flex: 1 1 100%;
      justify-content: flex-end;
    }
  }
</style>
