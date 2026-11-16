import { X, FlaskConical, AlertTriangle, Info } from 'lucide-react';
import { useWorkspace } from '@/context/workspace-context';

export function GatingModal() {
  const {
    gatingDialogOpen,
    gatingReason,
    closeGatingDialog,
    analyzeSource,
    startGuidedLab,
  } = useWorkspace();

  if (!gatingDialogOpen) return null;

  const handleAnalyze = async () => {
    closeGatingDialog();
    const success = await analyzeSource();
    if (success) {
      startGuidedLab();
    }
  };

  let title = 'Analyze your source first';
  let description =
    'Guided Lab requires an active analysis of your assembly source. Click "Analyze source" below to run the compiler pipeline.';
  let badge = 'AWAITING ANALYSIS';

  if (gatingReason === 'STALE') {
    title = 'Source changed';
    description =
      'Source changed. Re-analyze before entering Guided Lab.';
    badge = 'ANALYSIS STALE';
  } else if (gatingReason === 'ERROR') {
    title = 'Compiler errors detected';
    description =
      'Resolve compiler errors and re-analyze before entering Guided Lab.';
    badge = 'COMPILER ERRORS';
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
      data-testid="modal-gating"
    >
      <div
        className="panel"
        style={{
          maxWidth: 460,
          width: '100%',
          padding: '24px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
          border: '1px solid hsl(var(--border))',
          borderRadius: 8,
          background: 'hsl(var(--card))',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 14,
          }}
        >
          <span
            className="waiting-chip"
            style={{
              color:
                gatingReason === 'ERROR'
                  ? 'hsl(var(--destructive))'
                  : 'hsl(var(--accent))',
            }}
          >
            {gatingReason === 'ERROR' ? (
              <AlertTriangle size={11} style={{ marginRight: 4, display: 'inline' }} />
            ) : (
              <Info size={11} style={{ marginRight: 4, display: 'inline' }} />
            )}
            {badge}
          </span>
          <button
            className="icon-button"
            onClick={closeGatingDialog}
            aria-label="Close dialog"
            data-testid="button-gating-close"
          >
            <X size={15} />
          </button>
        </div>
        <h3
          style={{
            fontSize: 16,
            fontWeight: 600,
            marginBottom: 8,
            color: 'hsl(var(--foreground))',
          }}
          data-testid="text-gating-title"
        >
          {title}
        </h3>
        <p
          style={{
            fontSize: 13,
            color: 'hsl(var(--muted-foreground))',
            lineHeight: 1.5,
            marginBottom: 20,
          }}
          data-testid="text-gating-description"
        >
          {description}
        </p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button
            className="ghost-button"
            onClick={closeGatingDialog}
            data-testid="button-gating-cancel"
          >
            Cancel
          </button>
          <button
            className="primary-button"
            onClick={handleAnalyze}
            data-testid="button-gating-analyze"
          >
            <FlaskConical size={13} /> Analyze source
          </button>
        </div>
      </div>
    </div>
  );
}

export function UnsavedChangesModal() {
  const {
    unsavedDialogOpen,
    closeUnsavedDialog,
    confirmDiscardUnsaved,
    confirmSaveAndProceed,
    fileName,
  } = useWorkspace();

  if (!unsavedDialogOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
      data-testid="modal-unsaved"
    >
      <div
        className="panel"
        style={{
          maxWidth: 460,
          width: '100%',
          padding: '24px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
          border: '1px solid hsl(var(--border))',
          borderRadius: 8,
          background: 'hsl(var(--card))',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 14,
          }}
        >
          <span
            className="waiting-chip"
            style={{ color: 'hsl(var(--destructive))' }}
          >
            <AlertTriangle size={11} style={{ marginRight: 4, display: 'inline' }} />
            UNSAVED CHANGES
          </span>
          <button
            className="icon-button"
            onClick={closeUnsavedDialog}
            aria-label="Close dialog"
            data-testid="button-unsaved-close"
          >
            <X size={15} />
          </button>
        </div>
        <h3
          style={{
            fontSize: 16,
            fontWeight: 600,
            marginBottom: 8,
            color: 'hsl(var(--foreground))',
          }}
        >
          Unsaved changes in {fileName}
        </h3>
        <p
          style={{
            fontSize: 13,
            color: 'hsl(var(--muted-foreground))',
            lineHeight: 1.5,
            marginBottom: 20,
          }}
        >
          You have unsaved changes. Create a new file or open another file?
        </p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button
            className="ghost-button"
            onClick={closeUnsavedDialog}
            data-testid="button-unsaved-cancel"
          >
            Cancel
          </button>
          <button
            className="ghost-button"
            style={{ color: 'hsl(var(--destructive))' }}
            onClick={confirmDiscardUnsaved}
            data-testid="button-unsaved-discard"
          >
            Discard Changes
          </button>
          <button
            className="primary-button"
            onClick={() => void confirmSaveAndProceed()}
            data-testid="button-unsaved-save"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
