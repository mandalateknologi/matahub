<script lang="ts">
  import { onMount } from "svelte";
  import { apiKeysAPI } from "../lib/api/apiKeys";
  import { uiStore } from "../lib/stores/uiStore";
  import LoadingSpinner from "../lib/components/shared/LoadingSpinner.svelte";
  import Card from "../lib/components/shared/Card.svelte";
  import Button from "../lib/components/shared/Button.svelte";
  import ThemeToggle from "../lib/components/shared/ThemeToggle.svelte";
  import type { ApiKey, ApiKeyCreateResponse } from "@/lib/types";

  let loading = $state(true);
  let apiKey = $state<ApiKey | null>(null);
  let showGenerateModal = $state(false);
  let generatedKey = $state<ApiKeyCreateResponse | null>(null);
  let showRevokeConfirm = $state(false);
  let actionInProgress = $state(false);
  let copySuccess = $state(false);

  onMount(() => {
    loadApiKey();
  });

  async function loadApiKey() {
    try {
      loading = true;
      apiKey = await apiKeysAPI.getCurrent();
    } catch (error: any) {
      // 404 is expected if no key exists
      if (error.response?.status !== 404) {
        console.error("Error loading API key:", error);
        uiStore.showToast(
          error.response?.data?.detail || "Failed to load API key",
          "error",
        );
      }
    } finally {
      loading = false;
    }
  }

  async function handleGenerateKey() {
    try {
      actionInProgress = true;
      generatedKey = await apiKeysAPI.generate();
      apiKey = generatedKey; // Update local state
      showGenerateModal = true;
      uiStore.showToast("API key generated successfully!", "success");
    } catch (error: any) {
      console.error("Error generating API key:", error);
      uiStore.showToast(
        error.response?.data?.detail || "Failed to generate API key",
        "error",
      );
    } finally {
      actionInProgress = false;
    }
  }

  async function handleRevokeKey() {
    try {
      actionInProgress = true;
      await apiKeysAPI.revoke();
      apiKey = null;
      showRevokeConfirm = false;
      uiStore.showToast("API key revoked successfully", "success");
    } catch (error: any) {
      console.error("Error revoking API key:", error);
      uiStore.showToast(
        error.response?.data?.detail || "Failed to revoke API key",
        "error",
      );
    } finally {
      actionInProgress = false;
    }
  }

  function copyToClipboard() {
    if (generatedKey?.key) {
      navigator.clipboard.writeText(generatedKey.key);
      copySuccess = true;
      setTimeout(() => {
        copySuccess = false;
      }, 2000);
    }
  }

  function closeGenerateModal() {
    showGenerateModal = false;
    generatedKey = null;
  }

  function formatDate(dateString: string | null): string {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleString();
  }
</script>

<div class="settings-container">
  <div class="settings-header">
    <h1>Settings</h1>
    <ThemeToggle />
  </div>

  {#if loading}
    <LoadingSpinner />
  {:else}
    <!-- API Key Management Section -->
    <section class="settings-section">
      <h2>🔑 API Key Management</h2>
      <p class="section-description">
        Manage your API key for programmatic access to ATVISION. Use the API key
        in the <code>X-API-Key</code> header for authentication.
      </p>

      {#if apiKey}
        <!-- Existing API Key Display -->
        <div class="api-key-card">
          <div class="key-info">
            <div class="info-row">
              <span class="label">Key Prefix:</span>
              <code class="key-prefix">atv_{apiKey.key_prefix}...</code>
            </div>
            <div class="info-row">
              <span class="label">Created:</span>
              <span>{formatDate(apiKey.created_at)}</span>
            </div>
            <div class="info-row">
              <span class="label">Last Used:</span>
              <span>{formatDate(apiKey.last_used_at)}</span>
            </div>
          </div>

          <div class="key-actions">
            <button
              class="btn btn-danger"
              onclick={() => (showRevokeConfirm = true)}
              disabled={actionInProgress}
            >
              {actionInProgress ? "Revoking..." : "🗑️ Revoke Key"}
            </button>
          </div>
        </div>

        <div class="usage-instructions">
          <h3>Usage Instructions</h3>
          <p>Include your API key in the request header:</p>
          <pre><code
              >curl -H "X-API-Key: atv_your_key_here" http://localhost:8082/api/...</code
            ></pre>
          <p class="warning-text">
            ⚠️ <strong>Security Notice:</strong> Never commit your API key to version
            control or share it publicly. Treat it like a password!
          </p>
        </div>
      {:else}
        <!-- No API Key -->
        <div class="no-key-card">
          <p>You don't have an API key yet.</p>
          <button
            class="btn btn-primary"
            onclick={handleGenerateKey}
            disabled={actionInProgress}
          >
            {actionInProgress ? "Generating..." : "➕ Generate API Key"}
          </button>
        </div>
      {/if}
    </section>
  {/if}
</div>

<!-- Generate Key Modal -->
{#if showGenerateModal && generatedKey}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="modal-overlay" onclick={closeGenerateModal}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-content" onclick={(e) => e.stopPropagation()}>
      <h2>🎉 API Key Generated!</h2>
      <p class="warning-text">
        ⚠️ <strong>Important:</strong> This is the only time you'll see the full
        API key. Copy it now and store it securely!
      </p>

      <div class="key-display">
        <code>{generatedKey.key}</code>
        <button class="btn btn-secondary copy-btn" onclick={copyToClipboard}>
          {copySuccess ? "✓ Copied!" : "📋 Copy"}
        </button>
      </div>

      <div class="modal-actions">
        <button class="btn btn-primary" onclick={closeGenerateModal}>
          I've Saved My Key
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Revoke Confirmation Modal -->
{#if showRevokeConfirm}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="modal-overlay" onclick={() => (showRevokeConfirm = false)}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-content" onclick={(e) => e.stopPropagation()}>
      <h2>🗑️ Revoke API Key?</h2>
      <p>
        Are you sure you want to revoke your API key? This action is immediate
        and irreversible. Any applications using this key will be unable to
        authenticate.
      </p>

      <div class="modal-actions">
        <button
          class="btn btn-secondary"
          onclick={() => (showRevokeConfirm = false)}
          disabled={actionInProgress}
        >
          Cancel
        </button>
        <button
          class="btn btn-danger"
          onclick={handleRevokeKey}
          disabled={actionInProgress}
        >
          {actionInProgress ? "Revoking..." : "Revoke Key"}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .settings-container {
    padding: var(--spacing-xl);
    max-width: 1000px;
  }

  .settings-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-xl);
  }

  .settings-header h1 {
    margin: 0;
  }

  h1 {
    color: var(--color-navy);
    font-size: var(--font-size-3xl);
  }

  .settings-section {
    background: var(--color-bg-card);
    border-radius: var(--radius-lg);
    padding: var(--spacing-xl);
    box-shadow: var(--shadow-md);
    margin-bottom: var(--spacing-xl);
  }

  h2 {
    color: var(--color-navy);
    margin-bottom: var(--spacing-md);
    font-size: var(--font-size-2xl);
  }

  h3 {
    color: var(--color-navy);
    margin-bottom: var(--spacing-sm);
    font-size: var(--font-size-lg);
  }

  .section-description {
    color: var(--color-text-secondary);
    margin-bottom: var(--spacing-lg);
    line-height: 1.6;
  }

  .section-description code {
    background: var(--color-bg-hover);
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--radius-xs);
    font-family: var(--font-mono);
    font-size: 0.9em;
  }

  /* API Key Card */
  .api-key-card {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--spacing-lg);
    margin-bottom: var(--spacing-lg);
  }

  .key-info {
    margin-bottom: var(--spacing-md);
  }

  .info-row {
    display: flex;
    align-items: center;
    padding: var(--spacing-sm) 0;
    gap: var(--spacing-md);
  }

  .label {
    font-weight: 600;
    color: var(--color-navy);
    min-width: 100px;
  }

  .key-prefix {
    background: var(--color-bg-hover);
    padding: 4px 8px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.95em;
  }

  .key-actions {
    display: flex;
    gap: var(--spacing-md);
    padding-top: var(--spacing-md);
    border-top: 1px solid #e1e4e8;
  }

  /* No Key Card */
  .no-key-card {
    text-align: center;
    padding: var(--spacing-xl);
    border: 2px dashed #e1e4e8;
    border-radius: 6px;
    margin-bottom: var(--spacing-lg);
  }

  .no-key-card p {
    color: var(--color-text-secondary);
    margin-bottom: var(--spacing-md);
  }

  /* Usage Instructions */
  .usage-instructions {
    background: var(--color-bg-card);
    padding: var(--spacing-lg);
    border-radius: 6px;
  }

  .usage-instructions pre {
    background: #2d3748;
    color: #e2e8f0;
    padding: var(--spacing-md);
    border-radius: 4px;
    overflow-x: auto;
    margin: var(--spacing-md) 0;
  }

  .usage-instructions code {
    font-family: monospace;
    font-size: 0.9em;
  }

  .warning-text {
    color: #e1604c;
    font-size: 0.9em;
    margin-top: var(--spacing-md);
  }

  .warning-text strong {
    font-weight: 600;
  }

  /* Modal Styles */
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
    padding: var(--spacing-xl);
    border-radius: 8px;
    max-width: 600px;
    width: 90%;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
  }

  .modal-content h2 {
    margin-bottom: var(--spacing-md);
  }

  .modal-content p {
    color: var(--color-text-secondary);
    margin-bottom: var(--spacing-lg);
    line-height: 1.6;
  }

  .key-display {
    display: flex;
    gap: var(--spacing-md);
    align-items: center;
    background: #f8f9fa;
    padding: var(--spacing-md);
    border-radius: 4px;
    margin-bottom: var(--spacing-lg);
  }

  .key-display code {
    flex: 1;
    font-family: monospace;
    font-size: 0.9em;
    word-break: break-all;
    color: var(--color-navy);
  }

  .copy-btn {
    flex-shrink: 0;
  }

  .modal-actions {
    display: flex;
    gap: var(--spacing-md);
    justify-content: flex-end;
  }

  /* Buttons */
  .btn {
    padding: var(--spacing-sm) var(--spacing-lg);
    border: none;
    border-radius: 4px;
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition-fast);
    font-size: 0.95em;
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-primary {
    background: var(--color-accent);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: #d15440;
  }

  .btn-secondary {
    background: #6c757d;
    color: white;
  }

  .btn-secondary:hover:not(:disabled) {
    background: #5a6268;
  }

  .btn-danger {
    background: #dc3545;
    color: white;
  }

  .btn-danger:hover:not(:disabled) {
    background: #c82333;
  }
</style>
