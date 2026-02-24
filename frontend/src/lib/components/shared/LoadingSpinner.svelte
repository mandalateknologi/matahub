<script lang="ts">
  export let size: "sm" | "md" | "lg" = "md";
  export let message: string = "Loading...";
</script>

<div class="loading-container">
  <div class="spinner" class:sm={size === "sm"} class:lg={size === "lg"}>
    <div class="spinner-circle"></div>
  </div>
  {#if message}
    <p class="loading-message">{message}</p>
  {/if}
</div>

<style>
  .loading-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--spacing-xxl);
    min-height: 200px;
  }

  .spinner {
    width: 48px;
    height: 48px;
    margin-bottom: var(--spacing-md);
  }

  .spinner.sm {
    width: 24px;
    height: 24px;
  }

  .spinner.lg {
    width: 64px;
    height: 64px;
  }

  .spinner-circle {
    width: 100%;
    height: 100%;
    border: 4px solid var(--color-light-grey);
    border-top-color: var(--color-accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  .loading-message {
    font-size: var(--font-size-base);
    color: var(--color-grey);
    font-weight: 500;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
