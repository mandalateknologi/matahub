// Router utilities for svelte-spa-router compatibility
import { push, pop, replace } from 'svelte-spa-router';

// Navigate function compatible with old svelte-routing API
export function navigate(path: string, options?: { replace?: boolean }) {
  if (options?.replace) {
    replace(path);
  } else {
    push(path);
  }
}

// Link component is handled by svelte-spa-router's use:link directive
export { link } from 'svelte-spa-router';
