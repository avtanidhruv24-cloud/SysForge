import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { demoSource, demoFileName } from '@/lib/sysforge-data';
import {
  compilerApi,
  type LexerResult,
  type SyntaxResult,
  type Pass1Result,
} from '@/services/compiler-api';

export type AnalysisStatus =
  | 'NO_ANALYSIS'
  | 'ANALYZING'
  | 'ANALYZED'
  | 'ERROR'
  | 'STALE';

export interface DiagnosticItem {
  stage: string;
  severity: 'ERROR' | 'WARNING' | 'INFO';
  message: string;
  line: number | null;
  column: number | null;
  code?: string;
  token_value?: string | null;
}

export interface WorkspaceContextType {
  // File state
  source: string;
  setSource: (newSource: string) => void;
  fileName: string;
  setFileName: (name: string) => void;
  isDirty: boolean;
  fileHandle: unknown | null;
  newFile: () => void;
  openFile: () => Promise<void>;
  saveFile: () => Promise<boolean>;
  saveFileAs: () => Promise<boolean>;

  // Analysis state
  analysisStatus: AnalysisStatus;
  analyzedResult: Pass1Result | null;
  lexResult: LexerResult | null;
  syntaxResult: SyntaxResult | null;
  diagnostics: DiagnosticItem[];
  analyzeSource: () => Promise<boolean>;

  // Guided Lab
  guided: boolean;
  startGuidedLab: () => void;
  exitGuidedLab: () => void;
  replayGuidedLab: () => void;

  // Modals & Gating
  gatingDialogOpen: boolean;
  gatingReason: 'NO_ANALYSIS' | 'STALE' | 'ERROR';
  closeGatingDialog: () => void;
  unsavedDialogOpen: boolean;
  closeUnsavedDialog: () => void;
  confirmDiscardUnsaved: () => void;
  confirmSaveAndProceed: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextType | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  // File state
  const [source, setSourceState] = useState<string>(demoSource);
  const [fileName, setFileName] = useState<string>(demoFileName);
  const [lastSavedSource, setLastSavedSource] = useState<string>(demoSource);
  const [isDirty, setIsDirty] = useState<boolean>(false);
  const fileHandleRef = useRef<any>(null);

  // Analysis state
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus>('NO_ANALYSIS');
  const [analyzedResult, setAnalyzedResult] = useState<Pass1Result | null>(null);
  const [lexResult, setLexResult] = useState<LexerResult | null>(null);
  const [syntaxResult, setSyntaxResult] = useState<SyntaxResult | null>(null);
  const [diagnostics, setDiagnostics] = useState<DiagnosticItem[]>([]);
  const sourceVersionRef = useRef<number>(1);
  const analyzedVersionRef = useRef<number | null>(null);

  // Guided lab
  const [guided, setGuided] = useState<boolean>(false);

  // Modals
  const [gatingDialogOpen, setGatingDialogOpen] = useState<boolean>(false);
  const [gatingReason, setGatingReason] = useState<'NO_ANALYSIS' | 'STALE' | 'ERROR'>('NO_ANALYSIS');
  const [unsavedDialogOpen, setUnsavedDialogOpen] = useState<boolean>(false);
  const pendingActionRef = useRef<(() => void) | null>(null);

  // Source editing handler with invalidation & dirty state tracking
  const setSource = useCallback((newSource: string) => {
    setSourceState(newSource);
    sourceVersionRef.current += 1;

    // Track dirty state
    setIsDirty(newSource !== lastSavedSource);

    // Invalidate analysis if currently ANALYZED
    setAnalysisStatus((prev) => {
      if (prev === 'ANALYZED') return 'STALE';
      if (prev === 'ERROR') return 'NO_ANALYSIS';
      return prev;
    });
  }, [lastSavedSource]);

  // Direct internal setter that bypasses dirty/stale side-effects
  const setSourceInternal = useCallback((newSource: string) => {
    setSourceState(newSource);
    sourceVersionRef.current += 1;
  }, []);

  // Save As operation
  const saveFileAs = useCallback(async (): Promise<boolean> => {
    let targetName = fileName;
    if (!targetName.toLowerCase().endsWith('.asm')) {
      targetName = `${targetName}.asm`;
    }
    if (typeof window !== 'undefined' && 'showSaveFilePicker' in window) {
      try {
        const handle = await (window as any).showSaveFilePicker({
          suggestedName: targetName,
          types: [
            {
              description: 'Assembly Files (*.asm)',
              accept: { 'text/plain': ['.asm'] },
            },
          ],
        });
        const writable = await handle.createWritable();
        await writable.write(source);
        await writable.close();
        fileHandleRef.current = handle;
        setFileName(handle.name);
        setLastSavedSource(source);
        setIsDirty(false);
        return true;
      } catch (err: any) {
        if (err.name === 'AbortError') return false;
      }
    }

    // Fallback: Blob download
    const blob = new Blob([source], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = targetName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    setFileName(targetName);
    setLastSavedSource(source);
    setIsDirty(false);
    return true;
  }, [fileName, source]);

  // Save operation
  const saveFile = useCallback(async (): Promise<boolean> => {
    if (fileHandleRef.current && typeof fileHandleRef.current.createWritable === 'function') {
      try {
        const writable = await fileHandleRef.current.createWritable();
        await writable.write(source);
        await writable.close();
        setLastSavedSource(source);
        setIsDirty(false);
        return true;
      } catch (err: any) {
        if (err.name === 'AbortError') return false;
        return await saveFileAs();
      }
    }
    return await saveFileAs();
  }, [saveFileAs, source]);

  // Actual New File action
  const doNewFile = useCallback(() => {
    fileHandleRef.current = null;
    setFileName('untitled.asm');
    setSourceInternal('');
    setLastSavedSource('');
    setIsDirty(false);
    setAnalysisStatus('NO_ANALYSIS');
    setAnalyzedResult(null);
    setLexResult(null);
    setSyntaxResult(null);
    setDiagnostics([]);
  }, [setSourceInternal]);

  // New File with unsaved changes check
  const newFile = useCallback(() => {
    if (isDirty) {
      pendingActionRef.current = () => doNewFile();
      setUnsavedDialogOpen(true);
      return;
    }
    doNewFile();
  }, [doNewFile, isDirty]);

  // Actual Open File action
  const doOpenFile = useCallback(async () => {
    if (typeof window !== 'undefined' && 'showOpenFilePicker' in window) {
      try {
        const [handle] = await (window as any).showOpenFilePicker({
          types: [
            {
              description: 'Assembly Source (*.asm, *.s, *.txt)',
              accept: { 'text/plain': ['.asm', '.s', '.txt'] },
            },
          ],
          multiple: false,
        });
        const file = await handle.getFile();
        const text = await file.text();
        fileHandleRef.current = handle;
        setFileName(file.name);
        setSourceInternal(text);
        setLastSavedSource(text);
        setIsDirty(false);
        setAnalysisStatus('NO_ANALYSIS');
        setAnalyzedResult(null);
        setLexResult(null);
        setSyntaxResult(null);
        setDiagnostics([]);
        return;
      } catch (err: any) {
        if (err.name === 'AbortError') return;
      }
    }

    // Hidden input fallback
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.asm,.s,.txt';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (file) {
        const text = await file.text();
        fileHandleRef.current = null;
        setFileName(file.name);
        setSourceInternal(text);
        setLastSavedSource(text);
        setIsDirty(false);
        setAnalysisStatus('NO_ANALYSIS');
        setAnalyzedResult(null);
        setLexResult(null);
        setSyntaxResult(null);
        setDiagnostics([]);
      }
    };
    input.click();
  }, [setSourceInternal]);

  // Open File with unsaved changes check
  const openFile = useCallback(async () => {
    if (isDirty) {
      pendingActionRef.current = () => {
        void doOpenFile();
      };
      setUnsavedDialogOpen(true);
      return;
    }
    await doOpenFile();
  }, [doOpenFile, isDirty]);

  // Discard unsaved changes and execute pending action
  const confirmDiscardUnsaved = useCallback(() => {
    setUnsavedDialogOpen(false);
    if (pendingActionRef.current) {
      const action = pendingActionRef.current;
      pendingActionRef.current = null;
      action();
    }
  }, []);

  // Save changes and execute pending action
  const confirmSaveAndProceed = useCallback(async () => {
    const saved = await saveFile();
    if (saved) {
      setUnsavedDialogOpen(false);
      if (pendingActionRef.current) {
        const action = pendingActionRef.current;
        pendingActionRef.current = null;
        action();
      }
    }
  }, [saveFile]);

  // Explicit Analyze Source pipeline
  const analyzeSource = useCallback(async (): Promise<boolean> => {
    setAnalysisStatus('ANALYZING');
    try {
      const [lexResp, parseResp, pass1Resp] = await Promise.all([
        compilerApi.lex(source),
        compilerApi.parse(source),
        compilerApi.assemblePass1(source),
      ]);

      setLexResult(lexResp.result ?? null);
      setSyntaxResult(parseResp.result ?? null);
      setAnalyzedResult(pass1Resp.result ?? null);

      const diags: DiagnosticItem[] = [
        ...(lexResp.result?.diagnostics ?? []),
        ...(parseResp.result?.diagnostics ?? []),
        ...(pass1Resp.result?.diagnostics ?? []),
      ];
      setDiagnostics(diags);

      const hasFatalErrors =
        !pass1Resp.result?.success ||
        diags.some((d) => d.severity === 'ERROR');

      if (hasFatalErrors) {
        setAnalysisStatus('ERROR');
        return false;
      }

      setAnalysisStatus('ANALYZED');
      analyzedVersionRef.current = sourceVersionRef.current;
      return true;
    } catch (err: any) {
      setAnalysisStatus('ERROR');
      const msg = err instanceof Error ? err.message : String(err);
      setDiagnostics([
        {
          stage: 'service',
          severity: 'ERROR',
          message: msg.includes('fetch') || msg.includes('Failed')
            ? 'Backend unavailable — ensure FastAPI server is running on http://127.0.0.1:8000'
            : msg,
          line: null,
          column: null,
        },
      ]);
      return false;
    }
  }, [source]);

  // Guided Lab Gating
  const startGuidedLab = useCallback(() => {
    if (analysisStatus === 'ANALYZED') {
      setGuided(true);
    } else if (analysisStatus === 'STALE') {
      setGatingReason('STALE');
      setGatingDialogOpen(true);
    } else if (analysisStatus === 'ERROR') {
      setGatingReason('ERROR');
      setGatingDialogOpen(true);
    } else {
      setGatingReason('NO_ANALYSIS');
      setGatingDialogOpen(true);
    }
  }, [analysisStatus]);

  const exitGuidedLab = useCallback(() => {
    setGuided(false);
  }, []);

  const replayGuidedLab = useCallback(() => {
    setGuided(true);
  }, []);

  return (
    <WorkspaceContext.Provider
      value={{
        source,
        setSource,
        fileName,
        setFileName,
        isDirty,
        fileHandle: fileHandleRef.current,
        newFile,
        openFile,
        saveFile,
        saveFileAs,
        analysisStatus,
        analyzedResult,
        lexResult,
        syntaxResult,
        diagnostics,
        analyzeSource,
        guided,
        startGuidedLab,
        exitGuidedLab,
        replayGuidedLab,
        gatingDialogOpen,
        gatingReason,
        closeGatingDialog: () => setGatingDialogOpen(false),
        unsavedDialogOpen,
        closeUnsavedDialog: () => {
          setUnsavedDialogOpen(false);
          pendingActionRef.current = null;
        },
        confirmDiscardUnsaved,
        confirmSaveAndProceed,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceContextType {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider');
  }
  return context;
}
