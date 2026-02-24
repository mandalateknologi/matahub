<script lang="ts">
  import Router from "svelte-spa-router";
  import { wrap } from "svelte-spa-router/wrap";
  import { onMount } from "svelte";
  import { authStore } from "./lib/stores/authStore";
  import { themeStore } from "$lib/stores/themeStore";
  import { navigate } from "./lib/router";
  import "./app.css";

  // Import pages
  import Login from "./routes/login/+page.svelte";
  import Home from "./routes/home/+page.svelte";
  import Datasets from "./routes/datasets/+page.svelte";
  import DatasetDetail from "./routes/datasets/[id]/+page.svelte";
  import Projects from "./routes/projects/+page.svelte";
  import ProjectNew from "./routes/projects/new/+page.svelte";
  import ProjectDetail from "./routes/projects/[id]/+page.svelte";
  import Models from "./routes/models/+page.svelte";
  import ModelDetail from "./routes/models/[id]/+page.svelte";
  import Training from "./routes/training/+page.svelte";
  import TrainingNew from "./routes/training/new/+page.svelte";
  import Predictions from "./routes/predictions/+page.svelte";
  import PredictionsCapture from "./routes/predictions/capture/+page.svelte";
  import PredictionsReports from "./routes/predictions/reports/+page.svelte";
  import PredictionsJobDetail from "./routes/predictions/jobs/[id]/+page.svelte";
  import Users from "./routes/users/+page.svelte";
  import Settings from "./routes/Settings.svelte";
  import Profile from "./routes/Profile.svelte";
  import RecognitionCatalogs from "./routes/recognition-catalogs/+page.svelte";
  import RecognitionCatalogDetail from "./routes/recognition-catalogs/[id]/+page.svelte";
  import VisionMask from "./routes/visionmask/+page.svelte";

  // Import layout components
  import Navbar from "./lib/components/layout/Navbar.svelte";
  import Sidebar from "./lib/components/layout/Sidebar.svelte";
  import Toast from "./lib/components/layout/Toast.svelte";
  import Modal from "./lib/components/layout/Modal.svelte";

  let isAuthenticated = false;

  authStore.subscribe((state) => {
    isAuthenticated = state.isAuthenticated;
  });

  // Define routes
  const routes = {
    "/": Home,
    "/home": Home,
    "/login": Login,
    "/datasets": Datasets,
    "/datasets/:id": wrap({
      component: DatasetDetail,
      props: (params: any) => {
        const datasetId = parseInt(params.id);
        return { id: datasetId };
      },
    }),
    "/projects": Projects,
    "/projects/new": ProjectNew,
    "/projects/:id": wrap({
      component: ProjectDetail,
      props: (params: any) => ({ id: parseInt(params.id) }),
    }),
    "/models": Models,
    "/models/:id": wrap({
      component: ModelDetail,
      props: (params: any) => ({ id: parseInt(params.id) }),
    }),
    "/training": Training,
    "/training/new": TrainingNew,
    "/predictions": Predictions,
    "/predictions/capture": PredictionsCapture,
    "/predictions/reports": PredictionsReports,
    "/predictions/jobs/:id": wrap({
      component: PredictionsJobDetail,
      props: (params: any) => ({ id: params.id }),
    }),
    "/recognition-catalogs": RecognitionCatalogs,
    "/recognition-catalogs/:id": wrap({
      component: RecognitionCatalogDetail,
      props: (params: any) => ({ id: parseInt(params.id) }),
    }),
    "/visionmask": VisionMask,
    "/users": Users,
    "/settings": Settings,
    "/profile": Profile,
    "*": Login, // Fallback route
  };

  onMount(async () => {
    // Initialize theme system
    themeStore.init();

    // Check authentication and fetch user data
    await authStore.checkAuth();

    // Redirect to login if not authenticated
    const currentPath = window.location.pathname;
    if (!isAuthenticated && currentPath !== "/login") {
      navigate("/login", { replace: true });
    } else if (isAuthenticated && currentPath === "/login") {
      navigate("/home", { replace: true });
    }
  });
</script>

<div class="app">
  <Toast />
  <Modal />

  {#if isAuthenticated}
    <Navbar />
    <div class="app-container">
      <Sidebar />
      <main class="main-content">
        <Router {routes} />
      </main>
    </div>
  {:else}
    <Router routes={{ "/login": Login, "*": Login }} />
  {/if}
</div>

<style>
  .app {
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .app-container {
    display: flex;
    flex: 1;
    overflow: hidden;
    min-height: 0;
  }

  .main-content {
    flex: 1;
    padding: var(--spacing-lg);
    overflow-y: auto;
    background-color: var(--color-bg-light1);
  }
</style>
