<script lang="ts">
  import { BaseEdge, getBezierPath } from "@xyflow/svelte";
  import type { EdgeProps } from "@xyflow/svelte";

  type $$Props = EdgeProps;

  export let id: $$Props["id"];
  export let sourceX: $$Props["sourceX"];
  export let sourceY: $$Props["sourceY"];
  export let targetX: $$Props["targetX"];
  export let targetY: $$Props["targetY"];
  export let sourcePosition: $$Props["sourcePosition"];
  export let targetPosition: $$Props["targetPosition"];
  export let markerEnd: $$Props["markerEnd"];
  export let style: $$Props["style"] = undefined;
  export let data: $$Props["data"] = undefined;
  export let selected: $$Props["selected"] = false;

  // Get edge path and label position
  $: [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  // Handle delete button click
  function handleDelete(event: MouseEvent) {
    event.stopPropagation();
    if (data?.onDelete) {
      data.onDelete(id);
    }
  }

  let isHovered = false;
</script>

<g
  on:mouseenter={() => (isHovered = true)}
  on:mouseleave={() => (isHovered = false)}
>
  <BaseEdge path={edgePath} {markerEnd} {style} />

  {#if isHovered || selected}
    <foreignObject
      x={labelX - 10}
      y={labelY - 10}
      width="20"
      height="20"
      class="edge-delete-button"
    >
      <button
        class="delete-btn"
        on:click={handleDelete}
        title="Delete connection"
      >
        ×
      </button>
    </foreignObject>
  {/if}
</g>

<style>
  .edge-delete-button {
    overflow: visible;
    pointer-events: all;
  }

  .delete-btn {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #ef4444;
    border: 2px solid white;
    color: white;
    font-size: 14px;
    font-weight: bold;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    line-height: 1;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    transition: all 0.2s ease;
  }

  .delete-btn:hover {
    background: #dc2626;
    transform: scale(1.2);
  }

  .delete-btn:active {
    transform: scale(1.1);
  }
</style>
