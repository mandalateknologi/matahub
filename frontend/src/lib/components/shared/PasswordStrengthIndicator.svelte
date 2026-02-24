<script lang="ts">
  /**
   * PasswordStrengthIndicator Component
   * Visual indicator for password strength with color-coded bars
   */
  import { profileAPI } from "$lib/api/profile";

  let { password = "" } = $props();
  
  let strength = $state(0);
  let label = $state("Very Weak");
  let message = $state("");
  let isChecking = $state(false);

  // Debounced password strength check
  let checkTimeout: number | null = null;
  
  $effect(() => {
    if (password.length > 0) {
      if (checkTimeout) clearTimeout(checkTimeout);
      
      checkTimeout = setTimeout(async () => {
        try {
          isChecking = true;
          const result = await profileAPI.checkPasswordStrength(password);
          strength = result.strength_score;
          label = result.strength_label;
          message = result.message;
        } catch (error) {
          console.error("Error checking password strength:", error);
        } finally {
          isChecking = false;
        }
      }, 300); // 300ms debounce
    } else {
      strength = 0;
      label = "Very Weak";
      message = "";
    }
    
    return () => {
      if (checkTimeout) clearTimeout(checkTimeout);
    };
  });

  // Get color based on strength
  function getColor(score: number): string {
    switch (score) {
      case 0:
      case 1:
        return "#ef4444"; // Red
      case 2:
        return "#f59e0b"; // Amber
      case 3:
        return "#10b981"; // Green
      case 4:
        return "#059669"; // Dark green
      default:
        return "#d1d5db"; // Gray
    }
  }

  // Get bars to fill
  function getFilledBars(score: number): boolean[] {
    return [
      score >= 1,
      score >= 2,
      score >= 3,
      score >= 4,
    ];
  }
</script>

{#if password.length > 0}
  <div class="strength-indicator">
    <div class="strength-bars">
      {#each getFilledBars(strength) as filled, i}
        <div 
          class="bar"
          class:filled
          style="background-color: {filled ? getColor(strength) : '#e5e7eb'}"
        ></div>
      {/each}
    </div>
    
    <div class="strength-info">
      <span class="strength-label" style="color: {getColor(strength)}">
        {label}
      </span>
      
      {#if message && !isChecking}
        <span class="strength-message">{message}</span>
      {/if}
    </div>
  </div>
{/if}

<style>
  .strength-indicator {
    margin-top: var(--spacing-sm);
  }

  .strength-bars {
    display: flex;
    gap: var(--spacing-xs);
    margin-bottom: var(--spacing-xs);
  }

  .bar {
    height: 4px;
    flex: 1;
    border-radius: var(--radius-xs);
    background-color: #e5e7eb;
    transition: background-color var(--transition-fast);
  }

  .bar.filled {
    transform: scaleY(1.2);
  }

  .strength-info {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-xs);
  }

  .strength-label {
    font-size: var(--font-size-sm);
    font-weight: 600;
  }

  .strength-message {
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
  }
</style>
