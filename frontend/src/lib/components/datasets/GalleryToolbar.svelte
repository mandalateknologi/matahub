<script lang="ts">
  import { createEventDispatcher } from "svelte";

  export let searchTerm: string = "";
  export let sortBy: string = "name_asc";
  export let labelFilter: string = "all";
  export let totalFiles: number = 0;
  export let filteredCount: number = 0;
  export let taskType: string = "detect";

  const dispatch = createEventDispatcher();

  const sortOptions = [
    { value: "name_asc", label: "Name (A-Z)" },
    { value: "name_desc", label: "Name (Z-A)" },
    { value: "size_asc", label: "Size (Smallest)" },
    { value: "size_desc", label: "Size (Largest)" },
  ];

  if (taskType === "detect") {
    sortOptions.push({ value: "boxes_desc", label: "Most Boxes" });
  }

  const labelFilterOptions = [
    { value: "all", label: "All Images" },
    { value: "labeled", label: "Labeled Only" },
    { value: "unlabeled", label: "Unlabeled Only" },
  ];

  function handleSearchInput(event: Event) {
    const target = event.target as HTMLInputElement;
    dispatch("searchChange", target.value);
  }

  function handleSortChange(event: Event) {
    const target = event.target as HTMLSelectElement;
    dispatch("sortChange", target.value);
  }

  function handleLabelFilterChange(event: Event) {
    const target = event.target as HTMLSelectElement;
    dispatch("labelFilterChange", target.value);
  }

  function clearSearch() {
    searchTerm = "";
    dispatch("searchChange", "");
  }

  function handleKeydown(event: KeyboardEvent) {
    if ((event.ctrlKey || event.metaKey) && event.key === "f") {
      event.preventDefault();
      const searchInput = document.querySelector(
        ".gallery-search-input"
      ) as HTMLInputElement;
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="gallery-toolbar">
  <div class="toolbar-left">
    <div class="search-box">
      <svg
        class="search-icon"
        xmlns="http://www.w3.org/2000/svg"
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <circle cx="11" cy="11" r="8"></circle>
        <path d="m21 21-4.35-4.35"></path>
      </svg>
      <input
        type="text"
        class="gallery-search-input"
        placeholder="Search images... (Ctrl+F)"
        value={searchTerm}
        on:input={handleSearchInput}
      />
      {#if searchTerm}
        <button
          class="clear-search-btn"
          on:click={clearSearch}
          title="Clear search"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      {/if}
    </div>

    <div class="results-count">
      <span class="count-text">
        Showing <strong>{filteredCount}</strong> of
        <strong>{totalFiles}</strong> images
      </span>
    </div>
  </div>

  <div class="toolbar-right">
    {#if taskType === "detect"}
      <div class="filter-group">
        <label for="label-filter">Filter:</label>
        <select
          id="label-filter"
          class="filter-select"
          value={labelFilter}
          on:change={handleLabelFilterChange}
        >
          {#each labelFilterOptions as option}
            <option value={option.value}>{option.label}</option>
          {/each}
        </select>
      </div>
    {/if}

    <div class="filter-group">
      <label for="sort-select">Sort by:</label>
      <select
        id="sort-select"
        class="filter-select"
        value={sortBy}
        on:change={handleSortChange}
      >
        {#each sortOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </div>
  </div>
</div>

<style>
  .gallery-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    padding: 1rem 1.5rem;
    background: var(--color-bg-card);
    border: 1px solid #e5e7eb;
    border-radius: var(--radius-md);
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
  }

  .toolbar-left {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    flex: 1;
    min-width: 300px;
  }

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .search-box {
    position: relative;
    flex: 1;
    max-width: 400px;
  }

  .search-icon {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--color-grey);
    pointer-events: none;
  }

  .gallery-search-input {
    width: 100%;
    padding: 0.625rem 2.5rem 0.625rem 2.75rem;
    border: 2px solid #e5e7eb;
    border-radius: var(--radius-sm);
    font-size: 0.9375rem;
    font-family: var(--font-primary);
    transition: all var(--transition-fast);
  }

  .gallery-search-input:focus {
    outline: none;
    border-color: var(--color-navy);
    box-shadow: 0 0 0 3px rgba(29, 47, 67, 0.1);
  }

  .clear-search-btn {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    padding: 0.25rem;
    cursor: pointer;
    color: var(--color-grey);
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: all var(--transition-fast);
  }

  .clear-search-btn:hover {
    background: #f3f4f6;
    color: var(--color-navy);
  }

  .results-count {
    white-space: nowrap;
  }

  .count-text {
    font-size: 0.875rem;
    color: var(--color-grey);
  }

  .count-text strong {
    color: var(--color-navy);
    font-weight: 600;
  }

  .filter-group {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .filter-group label {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-navy);
    white-space: nowrap;
  }

  .filter-select {
    padding: 0.5rem 0.75rem;
    border: 2px solid #e5e7eb;
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
    font-family: var(--font-primary);
    color: var(--color-navy);
    background: var(--color-bg-primary); 
    cursor: pointer;
    transition: all var(--transition-fast);
    min-width: 140px;
  }

  .filter-select:focus {
    outline: none;
    border-color: var(--color-navy);
    box-shadow: 0 0 0 3px rgba(29, 47, 67, 0.1);
  }

  .filter-select:hover {
    border-color: var(--color-accent);
  }

  @media (max-width: 768px) {
    .gallery-toolbar {
      flex-direction: column;
      align-items: stretch;
    }

    .toolbar-left,
    .toolbar-right {
      flex-direction: column;
      align-items: stretch;
      width: 100%;
    }

    .search-box {
      max-width: none;
    }

    .filter-group {
      justify-content: space-between;
    }

    .filter-select {
      flex: 1;
    }
  }
</style>
