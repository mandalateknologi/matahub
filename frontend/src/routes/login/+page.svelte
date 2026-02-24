<script lang="ts">
  import { navigate } from "../../lib/router";
  import { authStore } from "../../lib/stores/authStore";
  import { uiStore } from "../../lib/stores/uiStore";
  import Button from "../../lib/components/shared/Button.svelte";
  import Card from "../../lib/components/shared/Card.svelte";

  let email = "";
  let password = "";
  let loading = false;
  let error = "";

  async function handleLogin(e: Event) {
    e.preventDefault();
    error = "";
    loading = true;

    try {
      await authStore.login(email, password);
      uiStore.showToast("Login successful!", "success");
      navigate("/home", { replace: true });
    } catch (err: any) {
      error =
        err.response?.data?.detail ||
        "Login failed. Please check your credentials.";
      uiStore.showToast(error, "error");
    } finally {
      loading = false;
    }
  }
</script>

<div class="login-container">
  <Card variant="elevated" padding="xl" class="login-card">
    <div class="login-header">
      <h1>ATVISION</h1>
      <p class="subtitle">Computer Vision Intelligence Platform</p>
    </div>

    <form on:submit={handleLogin}>
      <div class="form-group">
        <label for="email">Email</label>
        <input
          id="email"
          type="email"
          bind:value={email}
          placeholder="admin@atvision.com"
          required
          disabled={loading}
        />
      </div>

      <div class="form-group">
        <label for="password">Password</label>
        <input
          id="password"
          type="password"
          bind:value={password}
          placeholder="Enter your password"
          required
          disabled={loading}
        />
      </div>

      {#if error}
        <div class="error-message">{error}</div>
      {/if}

      <Button
        variant="primary"
        size="lg"
        {loading}
        type="submit"
        class="btn-full-width"
      >
        {loading ? "Logging in..." : "Login"}
      </Button>
    </form>

    <div class="login-footer">
      <p class="text-muted text-center">
        Default credentials: admin@atvision.com / admin
      </p>
    </div>
  </Card>
</div>

<style>
  .login-container {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(
      135deg,
      var(--color-navy) 0%,
      var(--color-grey) 100%
    );
    padding: var(--spacing-lg);
  }

  :global(.login-card) {
    width: 100%;
    max-width: 440px;
    box-shadow: var(--shadow-xl);
    animation: anim-fade-in 0.5s ease;
  }

  .login-header {
    text-align: center;
    margin-bottom: var(--spacing-xl);
  }

  .login-header h1 {
    color: var(--color-navy);
    font-size: var(--font-size-3xl);
    font-weight: 700;
    margin-bottom: var(--spacing-sm);
    letter-spacing: 0.05em;
  }

  .subtitle {
    color: var(--color-grey);
    font-size: var(--font-size-sm);
    margin: 0;
  }

  .form-group {
    margin-bottom: var(--spacing-lg);
  }

  .form-group label {
    display: block;
    margin-bottom: var(--spacing-sm);
    font-weight: 500;
    color: var(--color-navy);
  }

  .form-group input {
    width: 100%;
    padding: var(--spacing-md);
    font-size: var(--font-size-base);
  }

  .error-message {
    background-color: var(--color-status-error-bg);
    color: var(--color-status-error-text);
    padding: var(--spacing-md);
    border-radius: var(--radius-sm);
    margin-bottom: var(--spacing-lg);
    font-size: var(--font-size-sm);
  }

  :global(.btn-full-width) {
    width: 100%;
    margin-top: var(--spacing-md);
  }

  .login-footer {
    margin-top: var(--spacing-lg);
    padding-top: var(--spacing-lg);
    border-top: 1px solid var(--color-border-light);
  }
</style>
