import { type ReactNode, useCallback } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import { EditorPage, ExecutionPage, GuidedBar, GuidedControls, Shell, StagePage } from '@/components/sysforge-components';
import { routeByPath } from '@/lib/sysforge-data';
import NotFound from '@/pages/not-found';
import { WorkspaceProvider, useWorkspace } from '@/context/workspace-context';
import { GatingModal, UnsavedChangesModal } from '@/components/workspace-modals';

const queryClient = new QueryClient();

function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

function RoutedSurface({ onReplay }: { onReplay: () => void }) {
  const [location] = useLocation();
  const stage = routeByPath(location);
  const { source, setSource } = useWorkspace();
  return (
    <>
      {location === '/' ? (
        <EditorPage source={source} onSourceChange={setSource} />
      ) : location === '/execution' ? (
        <ExecutionPage source={source} />
      ) : (
        <StagePage stage={stage} source={source} />
      )}
      {location !== '/' && (
        <div style={{ marginTop: 18, display: 'flex', justifyContent: 'flex-end' }}>
          <GuidedControls onReplay={onReplay} />
        </div>
      )}
    </>
  );
}

function Router() {
  const [location, setLocation] = useLocation();
  const { guided, exitGuidedLab, replayGuidedLab, startGuidedLab } = useWorkspace();

  const replay = useCallback(() => {
    replayGuidedLab();
    setLocation('/');
  }, [replayGuidedLab, setLocation]);

  return (
    <RoutedErrorBoundary>
      <Shell onStartGuided={startGuidedLab}>
        <Switch>
          <Route path="/"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/lexical"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/syntax"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/macro"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/pass-one"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/symbols"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/literals"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/pools"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/intermediate"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/pass-two"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/object-code"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/linker"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/loader"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/memory"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/result"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/ai"><RoutedSurface onReplay={replay} /></Route>
          <Route path="/execution"><RoutedSurface onReplay={replay} /></Route>
          <Route component={NotFound} />
        </Switch>
      </Shell>
      {guided && <GuidedBar onExit={exitGuidedLab} onReplay={replay} />}
      <GatingModal />
      <UnsavedChangesModal />
    </RoutedErrorBoundary>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <WorkspaceProvider>
            <Router />
          </WorkspaceProvider>
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;