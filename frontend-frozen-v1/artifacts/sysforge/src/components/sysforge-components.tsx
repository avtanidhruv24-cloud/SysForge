import { type ReactNode, useEffect, useState } from 'react';
import { Link, useLocation } from 'wouter';
import CodeMirror from '@uiw/react-codemirror';
import { StreamLanguage } from '@codemirror/language';
import { EditorView, highlightActiveLine } from '@codemirror/view';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Braces,
  Boxes,
  BrainCircuit,
  Cable,
  CheckCircle2,
  CircleHelp,
  Code2,
  Copy,
  Cpu,
  Database,
  FileCode2,
  FilePlus2,
  FlaskConical,
  FolderOpen,
  Gauge,
  GitBranch,
  Hash,
  Keyboard,
  Layers3,
  Menu,
  Network,
  Play,
  RotateCcw,
  Save,
  SaveAll,
  Search,
  Settings2,
  ShieldCheck,
  Table2,
  Terminal,
  X,
} from 'lucide-react';
import { labStages, routeByPath, stageRows, type LabStage } from '@/lib/sysforge-data';
import { useWorkspace } from '@/context/workspace-context';
import { getLineCount, getCharacterCount } from '@/lib/source-metrics';
import {
  compilerApi,
  type LexerResult,
  type SyntaxResult,
  type ParsedStatement,
  type Pass1Result,
  type SymbolTableEntry,
  type LiteralTableEntry,
  type PoolTableEntry,
  type IntermediateRecord,
  type LCTraceEntry,
} from '@/services/compiler-api';

const icons: Record<string, typeof Code2> = {
  source: FileCode2,
  lexical: Hash,
  syntax: Braces,
  macro: Boxes,
  pass: Layers3,
  symbols: Table2,
  literals: Database,
  pools: Network,
  intermediate: GitBranch,
  object: Code2,
  linker: Cable,
  loader: Gauge,
  memory: Activity,
  result: Terminal,
  ai: BrainCircuit,
  execution: Cpu,
};

const iconForStage = (stage: LabStage) => {
  if (stage.path === '/') return icons.source;
  if (stage.path === '/pass-one' || stage.path === '/pass-two') return icons.pass;
  const key = stage.path.slice(1).split('-')[0] ?? 'source';
  return icons[key] ?? Code2;
};

const assemblyLanguage = StreamLanguage.define({
  token(stream) {
    if (stream.eatSpace()) return null;
    if (stream.match(/;.*/)) {
      stream.skipToEnd();
      return 'comment';
    }
    if (stream.match(/^='[^']*'/)) return 'string';
    if (stream.match(/^(START|END|ORIGIN|EQU|LTORG)\b/)) return 'keyword';
    if (stream.match(/^(ADD|SUB|MULT|MOVER|MOVEM|COMP|BC|DIV|READ|PRINT|STOP)\b/)) return 'operator';
    if (stream.match(/^(DC|DS)\b/)) return 'def';
    if (stream.match(/^(AREG|BREG|CREG|DREG)\b/)) return 'typeName';
    if (stream.match(/^(LT|LE|EQ|GT|GE|ANY)\b/)) return 'atom';
    if (stream.match(/^\d+/)) return 'number';
    if (stream.match(/^[A-Z][A-Z0-9_]*/)) return 'variableName';
    stream.next();
    return null;
  },
});

function Brand() {
  return (
    <Link href="/" className="brand" data-testid="link-brand">
      <span className="brand-mark" aria-hidden="true"><Cpu size={15} /></span>
      <span>
        <span className="brand-word">SYSFORGE</span>
        <span className="brand-sub">SYSTEM PROGRAMMING LAB</span>
      </span>
    </Link>
  );
}

function Sidebar({ mobileOpen, onClose }: { mobileOpen: boolean; onClose: () => void }) {
  const [location] = useLocation();
  const groups = [
    { label: 'Authoring', stages: labStages.slice(0, 1) },
    { label: 'Front end', stages: labStages.slice(1, 4) },
    { label: 'Translation', stages: labStages.slice(4, 11) },
    { label: 'Runtime', stages: labStages.slice(11) },
  ];

  return (
    <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`} data-testid="sidebar">
      <Brand />
      {groups.map((group) => (
        <div className="side-section" key={group.label}>
          <div className="side-label">{group.label}</div>
          <nav className="nav-list" aria-label={`${group.label} navigation`}>
            {group.stages.map((stage) => {
              const Icon = iconForStage(stage);
              const active = location === stage.path;
              return (
                <Link
                  href={stage.path}
                  key={stage.path}
                  className={`nav-link ${active ? 'active' : ''}`}
                  onClick={onClose}
                  data-testid={`link-nav-${stage.shortLabel.toLowerCase().replace(' ', '-')}`}
                  aria-current={active ? 'page' : undefined}
                >
                  <span className="nav-index">{stage.icon}</span>
                  <Icon size={14} strokeWidth={1.65} />
                  <span>{stage.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      ))}
      <div className="side-footer" data-testid="status-service">
        <div className="side-footer-row"><span><span className="status-dot" />Workspace</span><span className="muted">LOCAL</span></div>
        <div className="side-footer-row"><span>Compiler API</span><span className="muted">OFFLINE</span></div>
      </div>
    </aside>
  );
}

function Header({ onMenu, onStartGuided }: { onMenu: () => void; onStartGuided: () => void }) {
  const [location] = useLocation();
  const stage = routeByPath(location);
  const { fileName, isDirty, analysisStatus, analyzeSource } = useWorkspace();
  return (
    <header className="topbar">
      <div className="crumb">
        <button className="icon-button mobile-menu" onClick={onMenu} aria-label="Open navigation" data-testid="button-open-navigation"><Menu size={16} /></button>
        <span>LAB /</span><strong>{stage.shortLabel}</strong>
        <span style={{ margin: '0 8px', color: 'hsl(var(--muted-foreground))' }}>•</span>
        <span style={{ fontSize: 12, fontFamily: 'var(--app-font-mono)', color: 'hsl(var(--foreground))' }} data-testid="text-topbar-filename">
          {fileName}{isDirty ? ' *' : ''}
        </span>
      </div>
      <div className="top-actions">
        {analysisStatus === 'ANALYZING' ? (
          <span className="waiting-chip" data-testid="status-topbar-analyzing">ANALYZING…</span>
        ) : analysisStatus === 'STALE' ? (
          <span className="waiting-chip" style={{ color: 'hsl(var(--accent))' }} data-testid="status-topbar-stale">SOURCE CHANGED</span>
        ) : analysisStatus === 'ERROR' ? (
          <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }} data-testid="status-topbar-error">ERRORS DETECTED</span>
        ) : analysisStatus === 'ANALYZED' ? (
          <span style={{ color: 'hsl(var(--primary))', font: '10px var(--app-font-mono)' }} data-testid="status-topbar-analyzed">✓ ANALYZED</span>
        ) : (
          <span className="waiting-chip" data-testid="status-topbar-no-analysis">AWAITING ANALYSIS</span>
        )}
        <button
          className="ghost-button"
          onClick={() => { void analyzeSource(); }}
          disabled={analysisStatus === 'ANALYZING'}
          data-testid="button-topbar-analyze-source"
          title="Analyze source with SysForge compiler"
        >
          <FlaskConical size={13} /> Analyze source
        </button>
        <button className="icon-button" aria-label="Keyboard shortcuts" title="Guided lab: Arrow keys, Enter, Escape" data-testid="button-shortcuts"><Keyboard size={14} /></button>
        <button className="ghost-button" onClick={onStartGuided} data-testid="button-start-guided"><Play size={13} /> Guided lab</button>
      </div>
    </header>
  );
}

function Pipeline() {
  const [location] = useLocation();
  const currentIndex = Math.max(0, labStages.findIndex((stage) => stage.path === location));
  const displayStages = labStages;
  return (
    <div className="pipeline-wrap" data-testid="pipeline">
      <div className="pipeline-head">
        <span className="pipeline-title">Transformation pipeline</span>
        <span className="pipeline-key">{String(currentIndex + 1).padStart(2, '0')} / {String(labStages.length).padStart(2, '0')} stages</span>
      </div>
      <div className="pipeline">
        {displayStages.map((stage, index) => (
          <div className="pipeline-node" key={stage.path}>
            <Link
              href={stage.path}
              className={`pipeline-step ${stage.path === location ? 'current' : ''}`}
              data-testid={`link-pipeline-${stage.shortLabel.toLowerCase().replace(' ', '-')}`}
              title={stage.label}
            >
              <span className="pipeline-dot" />
              <span className="pipeline-step-label">{stage.shortLabel}</span>
            </Link>
            {index < displayStages.length - 1 && <span className={`pipeline-link ${index < currentIndex ? 'done' : ''}`} />}
          </div>
        ))}
      </div>
    </div>
  );
}

export function Shell({ children, onStartGuided }: { children: ReactNode; onStartGuided: () => void }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  return (
    <div className="sysforge-app">
      <div className="app-grid">
        <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
        <div className="main-shell">
          <Header onMenu={() => setMobileOpen(true)} onStartGuided={onStartGuided} />
          <main className="content">
            <Pipeline />
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}

export function EmptyState({ title, description, label = 'Waiting for service', icon: Icon = Search }: { title: string; description: string; label?: string; icon?: typeof Search }) {
  return (
    <div className="empty-state" data-testid="state-empty">
      <div className="empty-icon"><Icon size={19} /></div>
      <div className="empty-title" data-testid="text-empty-title">{title}</div>
      <p className="empty-copy" data-testid="text-empty-description">{description}</p>
      <span className="waiting-chip" data-testid="status-waiting">{label}</span>
    </div>
  );
}

export function StageTable({ stage }: { stage: LabStage }) {
  const columns = stageRows[stage.path] ?? ['Field', 'Value', 'Source', 'Status'];
  return (
    <div className="panel stage-main" data-testid={`panel-table-${stage.shortLabel.toLowerCase().replace(' ', '-')}`}>
      <div className="panel-head">
        <div className="panel-title"><Table2 size={14} /> {stage.label} output</div>
        <span className="panel-meta">NO DATASET</span>
      </div>
      <EmptyState
        title={`${stage.label} is standing by`}
        description="This surface will show verified compiler output when the analysis service is connected. No values are inferred in the client."
        label={stage.path === '/ai' ? 'AI service not connected yet' : `${stage.label} not connected yet`}
        icon={stage.path === '/ai' ? BrainCircuit : Table2}
      />
      <div className="table-wrap" hidden>
        <table className="data-table">
          <thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
          <tbody><tr>{columns.map((column) => <td key={column}>—</td>)}</tr></tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// LexicalPage — wired to POST /api/v1/lex
// ---------------------------------------------------------------------------

function LexicalPage({ source }: { source: string }) {
  const { analysisStatus, lexResult, analyzeSource } = useWorkspace();
  const tokens = lexResult?.tokens ?? [];
  const diagnostics = lexResult?.diagnostics ?? [];
  const hasErrors = diagnostics.some((d) => d.severity === 'ERROR');
  const contentTokens = tokens.filter((t) => t.type !== 'COMMENT');
  const lineCount = getLineCount(source);
  const charCount = getCharacterCount(source);

  return (
    <>
      <div className="page-intro">
        <div>
          <div className="eyebrow">front-end / laboratory stage</div>
          <h1 className="page-title" data-testid="heading-stage">Lexical analysis</h1>
          <p className="page-description">See source become tokens and literals.</p>
        </div>
        <div className="top-actions">
          {analysisStatus === 'ANALYZING' && <span className="waiting-chip">ANALYZING…</span>}
          {analysisStatus === 'ANALYZED' && !hasErrors && (
            <span style={{ color: 'hsl(var(--primary))', font: '10px var(--app-font-mono)' }}>
              ✓ {contentTokens.length} TOKENS
            </span>
          )}
          {analysisStatus === 'ANALYZED' && hasErrors && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              ⚠ LEXICAL ERRORS
            </span>
          )}
          {analysisStatus === 'STALE' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--accent))' }}>
              ⚠ SOURCE CHANGED (STALE)
            </span>
          )}
          {analysisStatus === 'ERROR' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              ERRORS DETECTED
            </span>
          )}
          {analysisStatus === 'NO_ANALYSIS' && (
            <span className="waiting-chip">AWAITING ANALYSIS</span>
          )}
        </div>
      </div>
      <div className="stage-grid">
        <div className="panel stage-main" data-testid="panel-table-lexical">
          <div className="panel-head">
            <div className="panel-title"><Hash size={14} /> Lexical analysis output</div>
            <span className="panel-meta">
              {analysisStatus === 'ANALYZING'
                ? 'ANALYZING'
                : (analysisStatus === 'ANALYZED' || analysisStatus === 'STALE') && contentTokens.length > 0
                ? `${contentTokens.length} TOKENS`
                : 'NO DATASET'}
            </span>
          </div>
          {analysisStatus === 'NO_ANALYSIS' && (
            <div className="empty-state" data-testid="state-empty">
              <div className="empty-icon"><Hash size={19} /></div>
              <div className="empty-title" data-testid="text-empty-title">Lexical analysis is standing by</div>
              <p className="empty-copy" data-testid="text-empty-description">
                Click &quot;Analyze source&quot; in the header or below to tokenize the assembly source.
              </p>
              <button
                className="primary-button"
                style={{ marginTop: 12 }}
                onClick={() => { void analyzeSource(); }}
              >
                <FlaskConical size={13} /> Analyze source
              </button>
            </div>
          )}
          {analysisStatus === 'ANALYZING' && (
            <EmptyState
              title="Lexer running…"
              description="Sending source to the deterministic SysForge lexer."
              label="ANALYZING"
              icon={Hash}
            />
          )}
          {analysisStatus === 'ERROR' && contentTokens.length === 0 && (
            <EmptyState
              title="Lexical analysis unavailable"
              description="Compiler analysis encountered fatal errors or backend is unavailable."
              label="CHECK BACKEND"
              icon={Search}
            />
          )}
          {(analysisStatus === 'ANALYZED' || analysisStatus === 'STALE') && contentTokens.length === 0 && (
            <EmptyState
              title="No tokens produced"
              description="The source produced no lexical tokens."
              label="EMPTY RESULT"
              icon={Hash}
            />
          )}
          {(analysisStatus === 'ANALYZED' || analysisStatus === 'STALE' || (analysisStatus === 'ERROR' && contentTokens.length > 0)) && contentTokens.length > 0 && (
            <>
              {analysisStatus === 'STALE' && (
                <div style={{ padding: '8px 16px', background: 'hsl(var(--accent) / 0.1)', borderBottom: '1px solid hsl(var(--border))', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 12, color: 'hsl(var(--accent))' }}>⚠ Source modified — tokens may be outdated.</span>
                  <button className="ghost-button" style={{ padding: '2px 8px', fontSize: 11 }} onClick={() => { void analyzeSource(); }}>Re-analyze</button>
                </div>
              )}
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Line</th>
                      <th>Col</th>
                      <th>Type</th>
                      <th>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {contentTokens.map((tok, i) => (
                      <tr key={i}>
                        <td>{tok.line}</td>
                        <td>{tok.column}</td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)', fontSize: 10, color: 'hsl(var(--primary))' }}>{tok.type}</span></td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)' }}>{tok.value}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {diagnostics.length > 0 && (
            <div style={{ padding: '12px 15px', borderTop: '1px solid hsl(var(--border))' }}>
              <div style={{ marginBottom: 8, font: '10px var(--app-font-mono)', color: 'hsl(var(--muted-foreground))', textTransform: 'uppercase', letterSpacing: '.1em' }}>
                Diagnostics ({diagnostics.length})
              </div>
              {diagnostics.map((d, i) => (
                <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid hsl(var(--border))', font: '11px var(--app-font-mono)', color: d.severity === 'ERROR' ? 'hsl(var(--destructive))' : 'hsl(var(--accent))' }}>
                  [{d.severity}] {d.message}{d.line != null ? ` — line ${d.line}${d.column != null ? `, col ${d.column}` : ''}` : ''}
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="stage-side">
          <div className="panel metric-card" data-testid="card-stage-status">
            <div className="metric-label">Stage status</div>
            <div className="metric-value" style={{ color: (analysisStatus === 'ANALYZED' && !hasErrors) ? 'hsl(var(--primary))' : (analysisStatus === 'ERROR' || hasErrors) ? 'hsl(var(--destructive))' : undefined }}>
              {analysisStatus === 'ANALYZING'
                ? 'RUNNING'
                : analysisStatus === 'ANALYZED'
                ? (hasErrors ? 'ERRORS' : 'COMPLETED')
                : analysisStatus === 'STALE'
                ? 'STALE'
                : analysisStatus === 'ERROR'
                ? 'ERRORS'
                : 'WAITING'}
            </div>
            <div className="metric-note">
              {analysisStatus === 'ANALYZED'
                ? `${contentTokens.length} tokens · ${diagnostics.length} diagnostics`
                : analysisStatus === 'STALE'
                ? 'Source modified. Re-analyze to update tokens.'
                : 'Awaiting explicit source analysis.'}
            </div>
          </div>
          <div className="callout" data-testid="callout-stage-contract">
            <strong><CircleHelp size={13} /> Lexer contract</strong>
            <p>Source text → typed tokens with line and column positions. Comments are emitted but not forwarded to the parser.</p>
          </div>
          <div className="panel metric-card">
            <div className="metric-label">Input source</div>
            <div className="metric-value" style={{ color: 'hsl(var(--secondary-foreground))', fontSize: 14 }}>
              {lineCount} LINE{lineCount === 1 ? '' : 'S'}
            </div>
            <div className="metric-note">{charCount} chars</div>
          </div>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// SyntaxPage — wired to WorkspaceContext (POST /api/v1/parse)
// ---------------------------------------------------------------------------

function SyntaxPage({ source }: { source: string }) {
  const { analysisStatus, syntaxResult, analyzeSource } = useWorkspace();
  const statements = syntaxResult?.statements ?? [];
  const diagnostics = syntaxResult?.diagnostics ?? [];
  const errorCount = diagnostics.filter((d) => d.severity === 'ERROR').length;
  const lineCount = getLineCount(source);
  const charCount = getCharacterCount(source);

  const getMnemonic = (s: ParsedStatement) =>
    s.directive ?? s.imperative ?? s.declarative ?? '—';

  const getOperands = (s: ParsedStatement): string => {
    const parts: string[] = [];
    if (s.register) parts.push(s.register);
    if (s.condition_code) parts.push(s.condition_code);
    if (s.operand) parts.push(s.operand);
    return parts.join(', ') || '—';
  };

  return (
    <>
      <div className="page-intro">
        <div>
          <div className="eyebrow">front-end / laboratory stage</div>
          <h1 className="page-title" data-testid="heading-stage">Syntax analysis</h1>
          <p className="page-description">Inspect grammar and syntax decisions.</p>
        </div>
        <div className="top-actions">
          {analysisStatus === 'ANALYZING' && <span className="waiting-chip">PARSING…</span>}
          {analysisStatus === 'ANALYZED' && errorCount === 0 && (
            <span style={{ color: 'hsl(var(--primary))', font: '10px var(--app-font-mono)' }}>
              ✓ {statements.length} STATEMENTS
            </span>
          )}
          {analysisStatus === 'ANALYZED' && errorCount > 0 && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              ⚠ {errorCount} SYNTAX ERROR{errorCount !== 1 ? 'S' : ''}
            </span>
          )}
          {analysisStatus === 'STALE' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--accent))' }}>
              ⚠ SOURCE CHANGED (STALE)
            </span>
          )}
          {analysisStatus === 'ERROR' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              ERRORS DETECTED
            </span>
          )}
          {analysisStatus === 'NO_ANALYSIS' && (
            <span className="waiting-chip">AWAITING ANALYSIS</span>
          )}
        </div>
      </div>
      <div className="stage-grid">
        <div className="panel stage-main" data-testid="panel-table-syntax">
          <div className="panel-head">
            <div className="panel-title"><Braces size={14} /> Syntax analysis output</div>
            <span className="panel-meta">
              {analysisStatus === 'ANALYZING'
                ? 'PARSING'
                : (analysisStatus === 'ANALYZED' || analysisStatus === 'STALE') && statements.length > 0
                ? `${statements.length} STATEMENTS`
                : 'NO DATASET'}
            </span>
          </div>
          {analysisStatus === 'NO_ANALYSIS' && (
            <div className="empty-state" data-testid="state-empty">
              <div className="empty-icon"><Braces size={19} /></div>
              <div className="empty-title" data-testid="text-empty-title">Syntax analysis is standing by</div>
              <p className="empty-copy" data-testid="text-empty-description">
                Click &quot;Analyze source&quot; in the header or below to parse statements.
              </p>
              <button
                className="primary-button"
                style={{ marginTop: 12 }}
                onClick={() => { void analyzeSource(); }}
              >
                <FlaskConical size={13} /> Analyze source
              </button>
            </div>
          )}
          {analysisStatus === 'ANALYZING' && (
            <EmptyState
              title="Parser running…"
              description="Sending source to the deterministic SysForge parser."
              label="PARSING"
              icon={Braces}
            />
          )}
          {analysisStatus === 'ERROR' && statements.length === 0 && (
            <EmptyState
              title="Parser unavailable"
              description="Compiler analysis encountered fatal errors or backend is unavailable."
              label="CHECK BACKEND"
              icon={Search}
            />
          )}
          {(analysisStatus === 'ANALYZED' || analysisStatus === 'STALE') && statements.length === 0 && (
            <EmptyState
              title="No statements parsed"
              description="The source produced no parsed statements."
              label="EMPTY RESULT"
              icon={Braces}
            />
          )}
          {(analysisStatus === 'ANALYZED' || analysisStatus === 'STALE' || (analysisStatus === 'ERROR' && statements.length > 0)) && statements.length > 0 && (
            <>
              {analysisStatus === 'STALE' && (
                <div style={{ padding: '8px 16px', background: 'hsl(var(--accent) / 0.1)', borderBottom: '1px solid hsl(var(--border))', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 12, color: 'hsl(var(--accent))' }}>⚠ Source modified — statements may be outdated.</span>
                  <button className="ghost-button" style={{ padding: '2px 8px', fontSize: 11 }} onClick={() => { void analyzeSource(); }}>Re-analyze</button>
                </div>
              )}
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Line</th>
                      <th>Label</th>
                      <th>Class</th>
                      <th>Mnemonic</th>
                      <th>Operands</th>
                      <th>Valid</th>
                    </tr>
                  </thead>
                  <tbody>
                    {statements.map((s, i) => (
                      <tr key={i} style={s.is_valid ? undefined : { color: 'hsl(var(--destructive))' }}>
                        <td>{s.line_number}</td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)', color: s.label ? 'hsl(var(--accent))' : 'hsl(var(--muted-foreground))' }}>{s.label ?? '—'}</span></td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)', fontSize: 10, color: 'hsl(var(--primary))' }}>{s.statement_class ?? '—'}</span></td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)' }}>{getMnemonic(s)}</span></td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)' }}>{getOperands(s)}</span></td>
                        <td style={{ color: s.is_valid ? 'hsl(var(--primary))' : 'hsl(var(--destructive))' }}>{s.is_valid ? '✓' : '✗'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {diagnostics.length > 0 && (
            <div style={{ padding: '12px 15px', borderTop: '1px solid hsl(var(--border))' }}>
              <div style={{ marginBottom: 8, font: '10px var(--app-font-mono)', color: 'hsl(var(--muted-foreground))', textTransform: 'uppercase', letterSpacing: '.1em' }}>
                Syntax diagnostics ({diagnostics.length})
              </div>
              {diagnostics.map((d, i) => (
                <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid hsl(var(--border))', font: '11px var(--app-font-mono)', color: d.severity === 'ERROR' ? 'hsl(var(--destructive))' : 'hsl(var(--accent))' }}>
                  [{d.severity}] {d.message}{d.line != null ? ` — line ${d.line}${d.column != null ? `, col ${d.column}` : ''}` : ''}
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="stage-side">
          <div className="panel metric-card" data-testid="card-stage-status">
            <div className="metric-label">Stage status</div>
            <div className="metric-value" style={{ color: (analysisStatus === 'ANALYZED' && errorCount === 0) ? 'hsl(var(--primary))' : (analysisStatus === 'ERROR' || errorCount > 0) ? 'hsl(var(--destructive))' : undefined }}>
              {analysisStatus === 'ANALYZING'
                ? 'RUNNING'
                : analysisStatus === 'ANALYZED'
                ? (errorCount > 0 ? 'ERRORS' : 'COMPLETED')
                : analysisStatus === 'STALE'
                ? 'STALE'
                : analysisStatus === 'ERROR'
                ? 'ERRORS'
                : 'WAITING'}
            </div>
            <div className="metric-note">
              {analysisStatus === 'ANALYZED'
                ? `${statements.length} statements · ${errorCount} error${errorCount !== 1 ? 's' : ''}`
                : analysisStatus === 'STALE'
                ? 'Source modified. Re-analyze to update statements.'
                : 'Awaiting explicit source analysis.'}
            </div>
          </div>
          <div className="callout" data-testid="callout-stage-contract">
            <strong><CircleHelp size={13} /> Parser contract</strong>
            <p>Token stream → parsed statements with labels, mnemonics, and operand types. Undefined symbols are not parser errors.</p>
          </div>
          <div className="panel metric-card">
            <div className="metric-label">Input source</div>
            <div className="metric-value" style={{ color: 'hsl(var(--secondary-foreground))', fontSize: 14 }}>
              {lineCount} LINE{lineCount === 1 ? '' : 'S'}
            </div>
            <div className="metric-note">{charCount} chars</div>
          </div>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Pass-I Hook & Sub-Page Views (Phase 5)
// ---------------------------------------------------------------------------

function usePassOne(_source?: string) {
  const { analyzedResult, analysisStatus, diagnostics, analyzeSource } = useWorkspace();
  const status: 'idle' | 'loading' | 'ok' | 'error' =
    analysisStatus === 'ANALYZING'
      ? 'loading'
      : analysisStatus === 'ANALYZED' || analysisStatus === 'STALE'
      ? 'ok'
      : analysisStatus === 'ERROR'
      ? 'error'
      : 'idle';
  return {
    pass1Result: analyzedResult,
    status,
    errorMsg: 'Pass-I analysis unavailable. Run "Analyze source" or check backend.',
    analysisStatus,
    diagnostics,
    analyzeSource,
  };
}

export function StagePage({ stage, source = '' }: { stage: LabStage; source?: string }) {
  const { fileName } = useWorkspace();
  const lineCount = getLineCount(source);
  const charCount = getCharacterCount(source);

  if (stage.path === '/lexical') return <LexicalPage source={source} />;
  if (stage.path === '/syntax') return <SyntaxPage source={source} />;
  if (stage.path === '/pass-one') return <PassOnePage stage={stage} source={source} />;
  if (stage.path === '/symbols') return <SymbolsPage stage={stage} source={source} />;
  if (stage.path === '/literals') return <LiteralsPage stage={stage} source={source} />;
  if (stage.path === '/pools') return <PoolsPage stage={stage} source={source} />;
  if (stage.path === '/intermediate') return <IntermediatePage stage={stage} source={source} />;
  if (stage.path === '/ai') return <AIAssistantPage stage={stage} />;
  if (stage.path === '/result') return <FinalResultPage stage={stage} />;

  const Icon = iconForStage(stage);
  return (
    <>
      <div className="page-intro">
        <div>
          <div className="eyebrow">{stage.group} / laboratory stage</div>
          <h1 className="page-title" data-testid="heading-stage">{stage.label}</h1>
          <p className="page-description">{stage.description} The view is ready for a service response, but currently reports only what is known.</p>
        </div>
        <div className="top-actions">
          <button className="ghost-button" disabled title="Requires compiler service" data-testid="button-run-stage"><Play size={13} /> Run stage</button>
        </div>
      </div>
      <div className="stage-grid">
        <StageTable stage={stage} />
        <div className="stage-side">
          <div className="panel metric-card" data-testid="card-stage-status">
            <div className="metric-label">Stage status</div>
            <div className="metric-value">WAITING</div>
            <div className="metric-note">No analysis request has been sent.</div>
          </div>
          <div className="callout" data-testid="callout-stage-contract">
            <strong><CircleHelp size={13} /> Service contract</strong>
            <p>Expected input: source text plus stage options. Expected output: typed records with source spans. The API boundary is intentionally not mocked.</p>
          </div>
          <div className="panel metric-card">
            <div className="metric-label">Input source</div>
            <div className="metric-value" style={{ color: 'hsl(var(--secondary-foreground))' }}>DEMO</div>
            <div className="metric-note">{fileName} · read-only preview</div>
          </div>
        </div>
      </div>
    </>
  );
}

function PassOnePage({ stage, source = '' }: { stage: LabStage; source?: string }) {
  const { pass1Result, status, errorMsg, analysisStatus, analyzeSource } = usePassOne(source);
  const lcTrace = pass1Result?.lc_trace ?? [];
  const diagnostics = pass1Result?.diagnostics ?? [];
  const errorCount = diagnostics.filter((d) => d.severity === 'ERROR').length;
  const hasErrors = errorCount > 0;
  const lineCount = getLineCount(source);
  const charCount = getCharacterCount(source);

  return (
    <>
      <div className="page-intro">
        <div>
          <div className="eyebrow">Translation / assembler pipeline</div>
          <h1 className="page-title" data-testid="heading-pass-one">Assembler Pass-I</h1>
          <p className="page-description">Pass-I assigns locations and produces the symbol, literal, pool, and intermediate artifacts consumed by Pass-II.</p>
        </div>
        <div className="top-actions">
          {status === 'loading' && <span className="waiting-chip">ASSEMBLING…</span>}
          {status === 'ok' && !hasErrors && analysisStatus !== 'STALE' && (
            <span style={{ color: 'hsl(var(--primary))', font: '10px var(--app-font-mono)' }}>
              ✓ {lcTrace.length} LC STEPS
            </span>
          )}
          {status === 'ok' && hasErrors && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              ⚠ {errorCount} PASS-I ERROR{errorCount !== 1 ? 'S' : ''}
            </span>
          )}
          {analysisStatus === 'STALE' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--accent))' }}>
              ⚠ SOURCE CHANGED (STALE)
            </span>
          )}
          {status === 'error' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              SERVICE UNAVAILABLE
            </span>
          )}
          {status === 'idle' && (
            <span className="waiting-chip">AWAITING ANALYSIS</span>
          )}
          <button
            className="ghost-button"
            onClick={() => { void analyzeSource(); }}
            disabled={analysisStatus === 'ANALYZING'}
            title="Run Assembler Pass-I"
            data-testid="button-run-pass-one"
          >
            <Play size={13} /> Run Pass-I
          </button>
        </div>
      </div>
      <div className="pass-one-flow" data-testid="pass-one-flow">
        <div className="flow-column">
          {['Source statements', 'Location counter', 'Symbol processing'].map((label, index) => (
            <div className="flow-node" key={label}>
              <span className="flow-index">0{index + 1}</span>
              <span>{label}</span>
              {index < 2 && <ArrowRight className="flow-connector" size={14} />}
            </div>
          ))}
        </div>
        <div className="pass-one-core">
          <div className="pass-one-core-head"><Layers3 size={14} /> ASSEMBLER PASS-I</div>
          <div className="artifact-grid">
            <div className="artifact-node" data-testid="artifact-symtab">
              <span>SYMTAB</span>
              <small>{status === 'ok' && pass1Result ? `${pass1Result.symbol_table.length} ENTRIES` : 'WAITING'}</small>
            </div>
            <div className="artifact-node" data-testid="artifact-littab">
              <span>LITTAB</span>
              <small>{status === 'ok' && pass1Result ? `${pass1Result.literal_table.length} ENTRIES` : 'WAITING'}</small>
            </div>
            <div className="artifact-node" data-testid="artifact-pooltab">
              <span>POOLTAB</span>
              <small>{status === 'ok' && pass1Result ? `${pass1Result.pool_table.length} POOLS` : 'WAITING'}</small>
            </div>
            <div className="artifact-node" data-testid="artifact-intermediate-code">
              <span>INTERMEDIATE CODE</span>
              <small>{status === 'ok' && pass1Result ? `${pass1Result.intermediate_code.length} RECORDS` : 'WAITING'}</small>
            </div>
          </div>
        </div>
        <div className="pass-one-next"><ArrowRight size={15} /><span>Assembler Pass-II</span></div>
      </div>
      <div className="stage-grid">
        <div className="panel stage-main" data-testid="panel-pass-one-state">
          <div className="panel-head">
            <div className="panel-title"><Activity size={14} /> Location Counter & Statement Trace</div>
            <span className="panel-meta">
              {status === 'loading' ? 'ASSEMBLING' : status === 'ok' ? `${lcTrace.length} STATEMENTS` : 'NO INPUT'}
            </span>
          </div>
          {status === 'idle' && (
            <div className="empty-state" data-testid="state-empty">
              <div className="empty-icon"><Layers3 size={19} /></div>
              <div className="empty-title" data-testid="text-empty-title">Pass-I is standing by</div>
              <p className="empty-copy" data-testid="text-empty-description">
                Location counters and generated artifacts will appear after the analysis service processes the source.
              </p>
              <button
                className="primary-button"
                style={{ marginTop: 12 }}
                onClick={() => { void analyzeSource(); }}
              >
                <FlaskConical size={13} /> Analyze source
              </button>
            </div>
          )}
          {status === 'loading' && (
            <EmptyState
              title="Pass-I running…"
              description="Calculating location counter and generating symbol/literal/pool artifacts."
              label="ASSEMBLING"
              icon={Layers3}
            />
          )}
          {status === 'error' && (
            <EmptyState
              title="Pass-I unavailable"
              description={errorMsg}
              label="CHECK BACKEND"
              icon={Layers3}
            />
          )}
          {status === 'ok' && lcTrace.length === 0 && (
            <EmptyState
              title="No statements processed"
              description="The source produced no statements to assemble."
              label="EMPTY RESULT"
              icon={Layers3}
            />
          )}
          {status === 'ok' && lcTrace.length > 0 && (
            <>
              {analysisStatus === 'STALE' && (
                <div style={{ padding: '8px 16px', background: 'hsl(var(--accent) / 0.1)', borderBottom: '1px solid hsl(var(--border))', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 12, color: 'hsl(var(--accent))' }}>⚠ Source modified — artifacts may be outdated.</span>
                  <button className="ghost-button" style={{ padding: '2px 8px', fontSize: 11 }} onClick={() => { void analyzeSource(); }}>Re-analyze</button>
                </div>
              )}
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Line</th>
                      <th>LC Before</th>
                      <th>Statement</th>
                      <th>Action</th>
                      <th>LC After</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lcTrace.map((entry, idx) => (
                      <tr key={idx}>
                        <td>{entry.source_line}</td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)' }}>{entry.lc_before != null ? entry.lc_before : '—'}</span></td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)', fontWeight: 500 }}>{entry.statement}</span></td>
                        <td><span style={{ fontSize: 11, color: 'hsl(var(--muted-foreground))' }}>{entry.action}{entry.explanation ? ` — ${entry.explanation}` : ''}</span></td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)', color: 'hsl(var(--primary))' }}>{entry.lc_after != null ? entry.lc_after : '—'}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {status === 'ok' && diagnostics.length > 0 && (
            <div style={{ padding: '12px 15px', borderTop: '1px solid hsl(var(--border))' }}>
              <div style={{ marginBottom: 8, font: '10px var(--app-font-mono)', color: 'hsl(var(--muted-foreground))', textTransform: 'uppercase', letterSpacing: '.1em' }}>
                Diagnostics ({diagnostics.length})
              </div>
              {diagnostics.map((d, i) => (
                <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid hsl(var(--border))', font: '11px var(--app-font-mono)', color: d.severity === 'ERROR' ? 'hsl(var(--destructive))' : 'hsl(var(--accent))' }}>
                  [{d.severity}] {d.message}{d.line != null ? ` — line ${d.line}${d.column != null ? `, col ${d.column}` : ''}` : ''}
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="stage-side">
          <div className="panel metric-card" data-testid="card-stage-status">
            <div className="metric-label">Stage status</div>
            <div className="metric-value" style={{ color: status === 'ok' && !hasErrors ? 'hsl(var(--primary))' : status === 'error' ? 'hsl(var(--destructive))' : undefined }}>
              {status === 'loading'
                ? 'RUNNING'
                : analysisStatus === 'STALE'
                ? 'STALE'
                : status === 'ok'
                ? (hasErrors ? 'ERRORS' : 'COMPLETED')
                : status === 'error'
                ? 'UNAVAILABLE'
                : 'WAITING'}
            </div>
            <div className="metric-note">
              {status === 'ok' ? `${pass1Result?.processed_statement_count ?? 0} statements processed · start: ${pass1Result?.starting_address ?? '—'} · final LC: ${pass1Result?.final_location_counter ?? '—'}` : 'Pass-I runs on parsed AST.'}
            </div>
          </div>
          <div className="panel metric-card">
            <div className="metric-label">Artifact relationship</div>
            <div className="metric-value">1 → 4</div>
            <div className="metric-note">One Pass-I stream produces four inspectable artifacts.</div>
          </div>
          <div className="callout" data-testid="callout-stage-contract">
            <strong><CircleHelp size={13} /> Educational model</strong>
            <p>Tables and intermediate code are Pass-I artifacts, not separate assembler passes.</p>
          </div>
          <div className="panel metric-card">
            <div className="metric-label">Input source</div>
            <div className="metric-value" style={{ color: 'hsl(var(--secondary-foreground))', fontSize: 14 }}>
              {lineCount} LINE{lineCount === 1 ? '' : 'S'}
            </div>
            <div className="metric-note">{charCount} chars</div>
          </div>
        </div>
      </div>
    </>
  );
}

function SymbolsPage({ stage, source = '' }: { stage: LabStage; source?: string }) {
  const { pass1Result, status, errorMsg, analysisStatus, analyzeSource } = usePassOne(source);
  const symbols = pass1Result?.symbol_table ?? [];
  const diagnostics = pass1Result?.diagnostics ?? [];
  const errorCount = diagnostics.filter((d) => d.severity === 'ERROR').length;
  const hasErrors = errorCount > 0;
  const lineCount = getLineCount(source);
  const charCount = getCharacterCount(source);

  return (
    <>
      <div className="page-intro">
        <div>
          <div className="eyebrow">{stage.group} / laboratory stage</div>
          <h1 className="page-title" data-testid="heading-stage">{stage.label}</h1>
          <p className="page-description">{stage.description} Real Pass-I symbol table (SYMTAB).</p>
        </div>
        <div className="top-actions">
          {status === 'loading' && <span className="waiting-chip">ASSEMBLING…</span>}
          {status === 'ok' && !hasErrors && analysisStatus !== 'STALE' && (
            <span style={{ color: 'hsl(var(--primary))', font: '10px var(--app-font-mono)' }}>
              ✓ {symbols.length} SYMBOLS
            </span>
          )}
          {status === 'ok' && hasErrors && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              ⚠ ERRORS DETECTED
            </span>
          )}
          {analysisStatus === 'STALE' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--accent))' }}>
              ⚠ SOURCE CHANGED (STALE)
            </span>
          )}
          {status === 'error' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              SERVICE UNAVAILABLE
            </span>
          )}
          {status === 'idle' && (
            <span className="waiting-chip">AWAITING ANALYSIS</span>
          )}
        </div>
      </div>
      <div className="stage-grid">
        <div className="panel stage-main" data-testid="panel-table-symbols">
          <div className="panel-head">
            <div className="panel-title"><Table2 size={14} /> Symbol Table (SYMTAB)</div>
            <span className="panel-meta">
              {status === 'loading' ? 'ASSEMBLING' : (status === 'ok' || analysisStatus === 'STALE') ? `${symbols.length} SYMBOLS` : 'NO DATASET'}
            </span>
          </div>
          {status === 'idle' && (
            <div className="empty-state" data-testid="state-empty">
              <div className="empty-icon"><Table2 size={19} /></div>
              <div className="empty-title" data-testid="text-empty-title">Symbol Table is standing by</div>
              <p className="empty-copy" data-testid="text-empty-description">
                Click &quot;Analyze source&quot; in the header or below to extract and resolve symbols.
              </p>
              <button
                className="primary-button"
                style={{ marginTop: 12 }}
                onClick={() => { void analyzeSource(); }}
              >
                <FlaskConical size={13} /> Analyze source
              </button>
            </div>
          )}
          {status === 'loading' && (
            <EmptyState
              title="Resolving symbols…"
              description="Extracting labels and resolving memory addresses."
              label="ASSEMBLING"
              icon={Table2}
            />
          )}
          {status === 'error' && (
            <EmptyState
              title="Symbol Table unavailable"
              description={errorMsg}
              label="CHECK BACKEND"
              icon={Table2}
            />
          )}
          {status === 'ok' && symbols.length === 0 && (
            <EmptyState
              title="No symbols declared"
              description="The source program contains no labels or symbols."
              label="EMPTY TABLE"
              icon={Table2}
            />
          )}
          {status === 'ok' && symbols.length > 0 && (
            <>
              {analysisStatus === 'STALE' && (
                <div style={{ padding: '8px 16px', background: 'hsl(var(--accent) / 0.1)', borderBottom: '1px solid hsl(var(--border))', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 12, color: 'hsl(var(--accent))' }}>⚠ Source modified — symbols may be outdated.</span>
                  <button className="ghost-button" style={{ padding: '2px 8px', fontSize: 11 }} onClick={() => { void analyzeSource(); }}>Re-analyze</button>
                </div>
              )}
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Value / Address</th>
                      <th>Defined At</th>
                      <th>Binding Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {symbols.map((sym, idx) => (
                      <tr key={idx}>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)', fontWeight: 600 }}>{sym.name}</span></td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)', color: 'hsl(var(--primary))' }}>{sym.is_defined ? sym.value : '—'}</span></td>
                        <td>{sym.defined_at_line != null ? `Line ${sym.defined_at_line}` : 'Unresolved'}</td>
                        <td>
                          <span style={{
                            fontFamily: 'var(--app-font-mono)',
                            fontSize: 10,
                            color: sym.is_defined ? 'hsl(var(--primary))' : 'hsl(var(--destructive))',
                          }}>
                            {sym.is_defined ? (sym.forward_reference ? 'RESOLVED (FWD)' : 'DEFINED') : 'UNDEFINED'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
        <div className="stage-side">
          <div className="panel metric-card" data-testid="card-stage-status">
            <div className="metric-label">Stage status</div>
            <div className="metric-value" style={{ color: status === 'ok' && !hasErrors ? 'hsl(var(--primary))' : status === 'error' ? 'hsl(var(--destructive))' : undefined }}>
              {status === 'loading'
                ? 'RUNNING'
                : analysisStatus === 'STALE'
                ? 'STALE'
                : status === 'ok'
                ? (hasErrors ? 'ERRORS' : 'COMPLETED')
                : status === 'error'
                ? 'UNAVAILABLE'
                : 'WAITING'}
            </div>
            <div className="metric-note">
              {status === 'ok' ? `${symbols.filter((s) => s.is_defined).length} defined · ${pass1Result?.unresolved_symbol_count ?? 0} unresolved` : 'Derived from Pass-I execution.'}
            </div>
          </div>
          <div className="callout" data-testid="callout-stage-contract">
            <strong><CircleHelp size={13} /> Service contract</strong>
            <p>Each label encountered in the source is assigned the value of the Location Counter (LC) at its definition point.</p>
          </div>
          <div className="panel metric-card">
            <div className="metric-label">Input source</div>
            <div className="metric-value" style={{ color: 'hsl(var(--secondary-foreground))', fontSize: 14 }}>
              {lineCount} LINE{lineCount === 1 ? '' : 'S'}
            </div>
            <div className="metric-note">{charCount} chars</div>
          </div>
        </div>
      </div>
    </>
  );
}

function LiteralsPage({ stage, source = '' }: { stage: LabStage; source?: string }) {
  const { pass1Result, status, errorMsg, analysisStatus, analyzeSource } = usePassOne(source);
  const literals = pass1Result?.literal_table ?? [];
  const diagnostics = pass1Result?.diagnostics ?? [];
  const errorCount = diagnostics.filter((d) => d.severity === 'ERROR').length;
  const hasErrors = errorCount > 0;
  const lineCount = getLineCount(source);
  const charCount = getCharacterCount(source);

  return (
    <>
      <div className="page-intro">
        <div>
          <div className="eyebrow">{stage.group} / laboratory stage</div>
          <h1 className="page-title" data-testid="heading-stage">{stage.label}</h1>
          <p className="page-description">{stage.description} Real Pass-I literal table (LITTAB).</p>
        </div>
        <div className="top-actions">
          {status === 'loading' && <span className="waiting-chip">ASSEMBLING…</span>}
          {status === 'ok' && !hasErrors && analysisStatus !== 'STALE' && (
            <span style={{ color: 'hsl(var(--primary))', font: '10px var(--app-font-mono)' }}>
              ✓ {literals.length} LITERALS
            </span>
          )}
          {status === 'ok' && hasErrors && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              ⚠ ERRORS DETECTED
            </span>
          )}
          {analysisStatus === 'STALE' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--accent))' }}>
              ⚠ SOURCE CHANGED (STALE)
            </span>
          )}
          {status === 'error' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              SERVICE UNAVAILABLE
            </span>
          )}
          {status === 'idle' && (
            <span className="waiting-chip">AWAITING ANALYSIS</span>
          )}
        </div>
      </div>
      <div className="stage-grid">
        <div className="panel stage-main" data-testid="panel-table-literals">
          <div className="panel-head">
            <div className="panel-title"><Database size={14} /> Literal Table (LITTAB)</div>
            <span className="panel-meta">
              {status === 'loading' ? 'ASSEMBLING' : (status === 'ok' || analysisStatus === 'STALE') ? `${literals.length} LITERALS` : 'NO DATASET'}
            </span>
          </div>
          {status === 'idle' && (
            <div className="empty-state" data-testid="state-empty">
              <div className="empty-icon"><Database size={19} /></div>
              <div className="empty-title" data-testid="text-empty-title">Literal Table is standing by</div>
              <p className="empty-copy" data-testid="text-empty-description">
                Click &quot;Analyze source&quot; in the header or below to collect and pool literals.
              </p>
              <button
                className="primary-button"
                style={{ marginTop: 12 }}
                onClick={() => { void analyzeSource(); }}
              >
                <FlaskConical size={13} /> Analyze source
              </button>
            </div>
          )}
          {status === 'loading' && (
            <EmptyState
              title="Pooling literals…"
              description="Allocating literal constants into memory pools."
              label="ASSEMBLING"
              icon={Database}
            />
          )}
          {status === 'error' && (
            <EmptyState
              title="Literal Table unavailable"
              description={errorMsg}
              label="CHECK BACKEND"
              icon={Database}
            />
          )}
          {status === 'ok' && literals.length === 0 && (
            <EmptyState
              title="No literals found"
              description="The source program contains no ='n' literal constants."
              label="EMPTY TABLE"
              icon={Database}
            />
          )}
          {status === 'ok' && literals.length > 0 && (
            <>
              {analysisStatus === 'STALE' && (
                <div style={{ padding: '8px 16px', background: 'hsl(var(--accent) / 0.1)', borderBottom: '1px solid hsl(var(--border))', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 12, color: 'hsl(var(--accent))' }}>⚠ Source modified — literals may be outdated.</span>
                  <button className="ghost-button" style={{ padding: '2px 8px', fontSize: 11 }} onClick={() => { void analyzeSource(); }}>Re-analyze</button>
                </div>
              )}
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Index</th>
                      <th>Literal</th>
                      <th>Pool</th>
                      <th>Address</th>
                      <th>Width</th>
                    </tr>
                  </thead>
                  <tbody>
                    {literals.map((lit, idx) => (
                      <tr key={idx}>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)' }}>#{lit.index ?? idx + 1}</span></td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)', color: 'hsl(var(--accent))' }}>{lit.value}</span></td>
                        <td>Pool #{lit.pool_index + 1}</td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)', color: 'hsl(var(--primary))' }}>{lit.address != null ? lit.address : 'PENDING'}</span></td>
                        <td>{lit.width}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
        <div className="stage-side">
          <div className="panel metric-card" data-testid="card-stage-status">
            <div className="metric-label">Stage status</div>
            <div className="metric-value" style={{ color: status === 'ok' && !hasErrors ? 'hsl(var(--primary))' : status === 'error' ? 'hsl(var(--destructive))' : undefined }}>
              {status === 'loading'
                ? 'RUNNING'
                : analysisStatus === 'STALE'
                ? 'STALE'
                : status === 'ok'
                ? (hasErrors ? 'ERRORS' : 'COMPLETED')
                : status === 'error'
                ? 'UNAVAILABLE'
                : 'WAITING'}
            </div>
            <div className="metric-note">
              {status === 'ok' ? `${literals.length} literals across ${pass1Result?.pool_count ?? 0} pool(s)` : 'Derived from Pass-I execution.'}
            </div>
          </div>
          <div className="callout" data-testid="callout-stage-contract">
            <strong><CircleHelp size={13} /> Service contract</strong>
            <p>Literals in the active pool are deduplicated. LTORG and END allocate unassigned literals at current LC.</p>
          </div>
          <div className="panel metric-card">
            <div className="metric-label">Input source</div>
            <div className="metric-value" style={{ color: 'hsl(var(--secondary-foreground))', fontSize: 14 }}>
              {lineCount} LINE{lineCount === 1 ? '' : 'S'}
            </div>
            <div className="metric-note">{charCount} chars</div>
          </div>
        </div>
      </div>
    </>
  );
}

function PoolsPage({ stage, source = '' }: { stage: LabStage; source?: string }) {
  const { pass1Result, status, errorMsg, analysisStatus, analyzeSource } = usePassOne(source);
  const pools = pass1Result?.pool_table ?? [];
  const diagnostics = pass1Result?.diagnostics ?? [];
  const errorCount = diagnostics.filter((d) => d.severity === 'ERROR').length;
  const hasErrors = errorCount > 0;
  const lineCount = getLineCount(source);
  const charCount = getCharacterCount(source);

  return (
    <>
      <div className="page-intro">
        <div>
          <div className="eyebrow">{stage.group} / laboratory stage</div>
          <h1 className="page-title" data-testid="heading-stage">{stage.label}</h1>
          <p className="page-description">{stage.description} Real Pass-I pool table (POOLTAB).</p>
        </div>
        <div className="top-actions">
          {status === 'loading' && <span className="waiting-chip">ASSEMBLING…</span>}
          {status === 'ok' && !hasErrors && analysisStatus !== 'STALE' && (
            <span style={{ color: 'hsl(var(--primary))', font: '10px var(--app-font-mono)' }}>
              ✓ {pools.length} POOLS
            </span>
          )}
          {status === 'ok' && hasErrors && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              ⚠ ERRORS DETECTED
            </span>
          )}
          {analysisStatus === 'STALE' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--accent))' }}>
              ⚠ SOURCE CHANGED (STALE)
            </span>
          )}
          {status === 'error' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              SERVICE UNAVAILABLE
            </span>
          )}
          {status === 'idle' && (
            <span className="waiting-chip">AWAITING ANALYSIS</span>
          )}
        </div>
      </div>
      <div className="stage-grid">
        <div className="panel stage-main" data-testid="panel-table-pools">
          <div className="panel-head">
            <div className="panel-title"><Network size={14} /> Pool Table (POOLTAB)</div>
            <span className="panel-meta">
              {status === 'loading' ? 'ASSEMBLING' : (status === 'ok' || analysisStatus === 'STALE') ? `${pools.length} POOLS` : 'NO DATASET'}
            </span>
          </div>
          {status === 'idle' && (
            <div className="empty-state" data-testid="state-empty">
              <div className="empty-icon"><Network size={19} /></div>
              <div className="empty-title" data-testid="text-empty-title">Pool Table is standing by</div>
              <p className="empty-copy" data-testid="text-empty-description">
                Click &quot;Analyze source&quot; in the header or below to mark literal pool boundaries.
              </p>
              <button
                className="primary-button"
                style={{ marginTop: 12 }}
                onClick={() => { void analyzeSource(); }}
              >
                <FlaskConical size={13} /> Analyze source
              </button>
            </div>
          )}
          {status === 'loading' && (
            <EmptyState
              title="Analyzing pools…"
              description="Evaluating literal pool boundaries and triggers."
              label="ASSEMBLING"
              icon={Network}
            />
          )}
          {status === 'error' && (
            <EmptyState
              title="Pool Table unavailable"
              description={errorMsg}
              label="CHECK BACKEND"
              icon={Network}
            />
          )}
          {status === 'ok' && pools.length === 0 && (
            <EmptyState
              title="No pools formed"
              description="The source program contains no literal pools."
              label="EMPTY TABLE"
              icon={Network}
            />
          )}
          {status === 'ok' && pools.length > 0 && (
            <>
              {analysisStatus === 'STALE' && (
                <div style={{ padding: '8px 16px', background: 'hsl(var(--accent) / 0.1)', borderBottom: '1px solid hsl(var(--border))', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 12, color: 'hsl(var(--accent))' }}>⚠ Source modified — pools may be outdated.</span>
                  <button className="ghost-button" style={{ padding: '2px 8px', fontSize: 11 }} onClick={() => { void analyzeSource(); }}>Re-analyze</button>
                </div>
              )}
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Pool</th>
                      <th>Starts at</th>
                      <th>Literal count</th>
                      <th>Boundary / Trigger</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pools.map((p, idx) => (
                      <tr key={idx}>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)', fontWeight: 600 }}>Pool #{p.pool_number}</span></td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)' }}>Index #{p.littab_start_index}</span></td>
                        <td>{p.literal_count} literal{p.literal_count !== 1 ? 's' : ''}</td>
                        <td><span style={{ fontSize: 11, color: 'hsl(var(--muted-foreground))' }}>{p.trigger ?? (p.ltorg_line ? `LTORG (line ${p.ltorg_line})` : 'END directive')}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
        <div className="stage-side">
          <div className="panel metric-card" data-testid="card-stage-status">
            <div className="metric-label">Stage status</div>
            <div className="metric-value" style={{ color: status === 'ok' && !hasErrors ? 'hsl(var(--primary))' : status === 'error' ? 'hsl(var(--destructive))' : undefined }}>
              {status === 'loading'
                ? 'RUNNING'
                : analysisStatus === 'STALE'
                ? 'STALE'
                : status === 'ok'
                ? (hasErrors ? 'ERRORS' : 'COMPLETED')
                : status === 'error'
                ? 'UNAVAILABLE'
                : 'WAITING'}
            </div>
            <div className="metric-note">
              {status === 'ok' ? `${pools.length} pool boundaries recorded` : 'Derived from Pass-I execution.'}
            </div>
          </div>
          <div className="callout" data-testid="callout-stage-contract">
            <strong><CircleHelp size={13} /> Service contract</strong>
            <p>Pool Table records starting indices into LITTAB for each pool created by LTORG or flushed at END.</p>
          </div>
          <div className="panel metric-card">
            <div className="metric-label">Input source</div>
            <div className="metric-value" style={{ color: 'hsl(var(--secondary-foreground))', fontSize: 14 }}>
              {lineCount} LINE{lineCount === 1 ? '' : 'S'}
            </div>
            <div className="metric-note">{charCount} chars</div>
          </div>
        </div>
      </div>
    </>
  );
}

function IntermediatePage({ stage, source = '' }: { stage: LabStage; source?: string }) {
  const { pass1Result, status, errorMsg, analysisStatus, analyzeSource } = usePassOne(source);
  const icRecords = pass1Result?.intermediate_code ?? [];
  const diagnostics = pass1Result?.diagnostics ?? [];
  const errorCount = diagnostics.filter((d) => d.severity === 'ERROR').length;
  const hasErrors = errorCount > 0;
  const lineCount = getLineCount(source);
  const charCount = getCharacterCount(source);

  return (
    <>
      <div className="page-intro">
        <div>
          <div className="eyebrow">{stage.group} / laboratory stage</div>
          <h1 className="page-title" data-testid="heading-stage">{stage.label}</h1>
          <p className="page-description">{stage.description} Real Pass-I intermediate code (IC).</p>
        </div>
        <div className="top-actions">
          {status === 'loading' && <span className="waiting-chip">ASSEMBLING…</span>}
          {status === 'ok' && !hasErrors && analysisStatus !== 'STALE' && (
            <span style={{ color: 'hsl(var(--primary))', font: '10px var(--app-font-mono)' }}>
              ✓ {icRecords.length} IC RECORDS
            </span>
          )}
          {status === 'ok' && hasErrors && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              ⚠ ERRORS DETECTED
            </span>
          )}
          {analysisStatus === 'STALE' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--accent))' }}>
              ⚠ SOURCE CHANGED (STALE)
            </span>
          )}
          {status === 'error' && (
            <span className="waiting-chip" style={{ color: 'hsl(var(--destructive))' }}>
              SERVICE UNAVAILABLE
            </span>
          )}
          {status === 'idle' && (
            <span className="waiting-chip">AWAITING ANALYSIS</span>
          )}
        </div>
      </div>
      <div className="stage-grid">
        <div className="panel stage-main" data-testid="panel-table-ir">
          <div className="panel-head">
            <div className="panel-title"><GitBranch size={14} /> Intermediate Code (IC)</div>
            <span className="panel-meta">
              {status === 'loading' ? 'ASSEMBLING' : (status === 'ok' || analysisStatus === 'STALE') ? `${icRecords.length} RECORDS` : 'NO DATASET'}
            </span>
          </div>
          {status === 'idle' && (
            <div className="empty-state" data-testid="state-empty">
              <div className="empty-icon"><GitBranch size={19} /></div>
              <div className="empty-title" data-testid="text-empty-title">Intermediate Code is standing by</div>
              <p className="empty-copy" data-testid="text-empty-description">
                Click &quot;Analyze source&quot; in the header or below to emit intermediate code representation.
              </p>
              <button
                className="primary-button"
                style={{ marginTop: 12 }}
                onClick={() => { void analyzeSource(); }}
              >
                <FlaskConical size={13} /> Analyze source
              </button>
            </div>
          )}
          {status === 'loading' && (
            <EmptyState
              title="Generating intermediate code…"
              description="Emitting machine-independent IR representation."
              label="ASSEMBLING"
              icon={GitBranch}
            />
          )}
          {status === 'error' && (
            <EmptyState
              title="Intermediate Code unavailable"
              description={errorMsg}
              label="CHECK BACKEND"
              icon={GitBranch}
            />
          )}
          {status === 'ok' && icRecords.length === 0 && (
            <EmptyState
              title="No IR records emitted"
              description="The source program produced no intermediate code records."
              label="EMPTY TABLE"
              icon={GitBranch}
            />
          )}
          {status === 'ok' && icRecords.length > 0 && (
            <>
              {analysisStatus === 'STALE' && (
                <div style={{ padding: '8px 16px', background: 'hsl(var(--accent) / 0.1)', borderBottom: '1px solid hsl(var(--border))', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 12, color: 'hsl(var(--accent))' }}>⚠ Source modified — IR may be outdated.</span>
                  <button className="ghost-button" style={{ padding: '2px 8px', fontSize: 11 }} onClick={() => { void analyzeSource(); }}>Re-analyze</button>
                </div>
              )}
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Line</th>
                      <th>LC</th>
                      <th>Class</th>
                      <th>Opcode</th>
                      <th>Mnemonic</th>
                      <th>Operand fields</th>
                    </tr>
                  </thead>
                  <tbody>
                    {icRecords.map((ic, idx) => (
                      <tr key={idx}>
                        <td>{ic.source_line}</td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)' }}>{ic.location_counter != null ? ic.location_counter : '—'}</span></td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)', color: 'hsl(var(--primary))' }}>({ic.statement_class})</span></td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)' }}>({ic.opcode_value != null ? String(ic.opcode_value).padStart(2, '0') : '--'})</span></td>
                        <td><span style={{ fontFamily: 'var(--app-font-mono)', fontWeight: 500 }}>{ic.mnemonic}</span></td>
                        <td>
                          <span style={{ fontFamily: 'var(--app-font-mono)' }}>
                            {ic.operands.length > 0
                              ? ic.operands.map((op) => `(${op.type}, ${op.value})`).join(' ')
                              : '—'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
        <div className="stage-side">
          <div className="panel metric-card" data-testid="card-stage-status">
            <div className="metric-label">Stage status</div>
            <div className="metric-value" style={{ color: status === 'ok' && !hasErrors ? 'hsl(var(--primary))' : status === 'error' ? 'hsl(var(--destructive))' : undefined }}>
              {status === 'loading'
                ? 'RUNNING'
                : analysisStatus === 'STALE'
                ? 'STALE'
                : status === 'ok'
                ? (hasErrors ? 'ERRORS' : 'COMPLETED')
                : status === 'error'
                ? 'UNAVAILABLE'
                : 'WAITING'}
            </div>
            <div className="metric-note">
              {status === 'ok' ? `${icRecords.length} records emitted · ready for Pass-II` : 'Derived from Pass-I execution.'}
            </div>
          </div>
          <div className="callout" data-testid="callout-stage-contract">
            <strong><CircleHelp size={13} /> Service contract</strong>
            <p>Intermediate Code encodes (Class, Opcode) tuples and operand descriptors: (R, reg#), (S, sym#), (L, lit#), (C, const).</p>
          </div>
          <div className="panel metric-card">
            <div className="metric-label">Input source</div>
            <div className="metric-value" style={{ color: 'hsl(var(--secondary-foreground))', fontSize: 14 }}>
              {lineCount} LINE{lineCount === 1 ? '' : 'S'}
            </div>
            <div className="metric-note">{charCount} chars</div>
          </div>
        </div>
      </div>
    </>
  );
}

function AIAssistantPage({ stage }: { stage: LabStage }) {
  const [tab, setTab] = useState<'explain' | 'optimize'>('explain');
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null);
  const prompts = [
    'Explain this token',
    'Explain this syntax error',
    'Explain this symbol',
    'Why was this symbol assigned this address?',
    'Explain this literal pool',
    'Explain this intermediate code',
    'Explain this machine instruction',
    'Explain this linker error',
    'Explain this memory location',
    'Explain this execution step',
  ];

  return (
    <>
      <div className="page-intro">
        <div>
          <div className="eyebrow">Intelligence / deterministic context</div>
          <h1 className="page-title" data-testid="heading-ai">AI Assistant</h1>
          <p className="page-description">An explanation and optimization layer grounded in verified SysForge results. It is not the assembler, parser, linker, or execution engine.</p>
        </div>
        <div className="top-actions"><span className="waiting-chip">SERVICE NOT CONNECTED</span></div>
      </div>
      <div className="ai-tabs" role="tablist" aria-label="AI assistant modes">
        <button className={`ai-tab ${tab === 'explain' ? 'active' : ''}`} onClick={() => setTab('explain')} role="tab" aria-selected={tab === 'explain'} data-testid="tab-ai-explain"><BrainCircuit size={14} /> Explain</button>
        <button className={`ai-tab ${tab === 'optimize' ? 'active' : ''}`} onClick={() => setTab('optimize')} role="tab" aria-selected={tab === 'optimize'} data-testid="tab-ai-optimize"><Settings2 size={14} /> Optimize</button>
      </div>
      {tab === 'explain' ? (
        <div className="ai-layout" data-testid="panel-ai-explain">
          <div className="panel ai-prompts">
            <div className="panel-head"><div className="panel-title"><BrainCircuit size={14} /> Suggested explanations</div><span className="panel-meta">CONTEXTUAL</span></div>
            <div className="prompt-list">
              {prompts.map((prompt) => <button className={`prompt-button ${selectedPrompt === prompt ? 'selected' : ''}`} key={prompt} onClick={() => setSelectedPrompt(prompt)} data-testid={`button-ai-prompt-${prompt.toLowerCase().replaceAll(' ', '-')}`}>{prompt}<ArrowRight size={13} /></button>)}
            </div>
          </div>
          <div className="panel ai-response">
            <div className="panel-head"><div className="panel-title"><Terminal size={14} /> Assistant response</div><span className="panel-meta">GROUNDED ONLY</span></div>
            <EmptyState title={selectedPrompt ? 'Explanation is waiting' : 'Select a question'} description={selectedPrompt ? `The service will answer “${selectedPrompt}” using the selected stage and verified analysis context.` : 'Choose a contextual question to request a grounded explanation from the AI service.'} label="AI explanation not connected yet" icon={BrainCircuit} />
          </div>
        </div>
      ) : (
        <div className="panel optimize-panel" data-testid="panel-ai-optimize">
          <div className="panel-head"><div className="panel-title"><Settings2 size={14} /> AI Optimization</div><span className="panel-meta">SUGGESTIONS ONLY</span></div>
          <div className="optimize-body">
            <div>
              <h2>Analyze the current program for possible improvements.</h2>
              <p>Recommendations will be grounded in deterministic engine output. Source code will never change without an explicit user action.</p>
            </div>
            <button className="primary-button" disabled title="Optimization engine not connected" data-testid="button-analyze-optimization"><Activity size={13} /> Analyze program</button>
          </div>
          <EmptyState title="No optimization opportunities yet" description="The optimization engine has not returned a verified suggestion for this analysis session." label="Optimization engine not connected yet" icon={Settings2} />
        </div>
      )}
      <div className="ai-integrity"><ShieldCheck size={14} /><span>Deterministic engine remains the source of truth. AI can explain or suggest, never silently compile or execute.</span></div>
    </>
  );
}

function FinalResultPage({ stage }: { stage: LabStage }) {
  const summary = ['Source status', 'Lexical analysis', 'Syntax analysis', 'Macro processing', 'Assembler Pass-I', 'Symbol table', 'Literal table', 'Pool table', 'Intermediate code', 'Assembler Pass-II', 'Object / Machine Code', 'Linker', 'Loader', 'Memory Map', 'AI Analysis', 'AI Optimization', 'Program Execution', 'Program Output'];
  return (
    <>
      <div className="page-intro">
        <div>
          <div className="eyebrow">Final / analysis session</div>
          <h1 className="page-title" data-testid="heading-result">SYSFORGE Analysis Complete</h1>
          <p className="page-description">A complete summary will be generated from the shared analysis session once the deterministic engine is connected.</p>
        </div>
        <span className="waiting-chip">NOT CONNECTED</span>
      </div>
      <div className="result-layout" data-testid="panel-final-result">
        <div className="panel summary-panel">
          <div className="panel-head"><div className="panel-title"><Table2 size={14} /> Analysis summary</div><span className="panel-meta">18 STAGES</span></div>
          <div className="summary-list">{summary.map((item) => <div className="summary-row" key={item}><span><span className="status-dot muted-dot" />{item}</span><span className="summary-status">NOT CONNECTED</span></div>)}</div>
        </div>
        <div className="result-side">
          <div className="panel metric-card"><div className="metric-label">Program status</div><div className="metric-value">WAITING</div><div className="metric-note">No execution result exists for this session.</div></div>
          <div className="panel output-panel"><div className="panel-head"><div className="panel-title"><Terminal size={14} /> Program output</div></div><EmptyState title="Waiting for program execution" description="Output will appear here only after the educational virtual machine returns a verified result." label="Execution not connected yet" icon={Terminal} /></div>
        </div>
      </div>
    </>
  );
}

export function EditorPage({ source, onSourceChange }: { source: string; onSourceChange: (value: string) => void }) {
  const {
    fileName,
    isDirty,
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
  } = useWorkspace();

  const [cursor, setCursor] = useState({ line: 1, col: 1 });
  const lineCount = getLineCount(source);
  const charCount = getCharacterCount(source);

  return (
    <>
      <div className="page-intro">
        <div>
          <div className="eyebrow">Workspace / source</div>
          <h1 className="page-title" data-testid="heading-home">Assembly laboratory</h1>
          <p className="page-description">A transparent path from assembly source to execution. Edit the specimen, then connect a compiler service when you are ready to inspect each transformation.</p>
        </div>
        <div className="top-actions">
          <button
            className="ghost-button"
            onClick={newFile}
            data-testid="button-new-file"
            title="Create a new assembly source file"
          >
            <FilePlus2 size={13} /> New File
          </button>
          <button
            className="ghost-button"
            onClick={() => { void openFile(); }}
            data-testid="button-open-file"
            title="Open an existing assembly file (*.asm, *.s, *.txt)"
          >
            <FolderOpen size={13} /> Open
          </button>
          <button
            className="ghost-button"
            onClick={() => { void saveFile(); }}
            data-testid="button-save-file"
            title="Save current file"
          >
            <Save size={13} /> Save
          </button>
          <button
            className="ghost-button"
            onClick={() => { void saveFileAs(); }}
            data-testid="button-save-as-file"
            title="Save as a new file"
          >
            <SaveAll size={13} /> Save As
          </button>
          <button
            className="ghost-button"
            onClick={() => void navigator.clipboard?.writeText(source)}
            data-testid="button-copy-source"
            title="Copy source to clipboard"
          >
            <Copy size={13} /> Copy source
          </button>
          <button
            className="primary-button"
            onClick={() => { void analyzeSource(); }}
            disabled={analysisStatus === 'ANALYZING'}
            data-testid="button-analyze-source"
            title="Run Lexer, Parser, and Assembler Pass-I"
          >
            <FlaskConical size={13} /> {analysisStatus === 'ANALYZING' ? 'Analyzing…' : 'Analyze source'}
          </button>
        </div>
      </div>
      <div className="editor-layout">
        <div className="panel" data-testid="panel-source-editor">
          <div className="panel-head">
            <div className="panel-title">
              <FileCode2 size={14} /> {fileName}{isDirty ? ' *' : ''}{' '}
              <span className="muted">{isDirty ? '/ unsaved' : '/ saved'}</span>
            </div>
            <span className="panel-meta">ASM · UTF-8</span>
          </div>
          <div className="editor code-editor" data-testid="input-source-editor">
            <CodeMirror
              value={source}
              height="385px"
              extensions={[assemblyLanguage, highlightActiveLine(), EditorView.lineWrapping]}
              onChange={onSourceChange}
              onUpdate={(viewUpdate) => {
                const head = viewUpdate.state.selection.main.head;
                const lineObj = viewUpdate.state.doc.lineAt(head);
                setCursor({
                  line: lineObj.number,
                  col: head - lineObj.from + 1,
                });
              }}
              basicSetup={{
                lineNumbers: true,
                foldGutter: false,
                highlightActiveLine: true,
                highlightActiveLineGutter: true,
                drawSelection: true,
                dropCursor: true,
              }}
              aria-label="Assembly source editor"
            />
          </div>
          <div className="editor-foot" data-testid="editor-status-bar">
            <span>Cursor <strong>{cursor.line}:{cursor.col}</strong></span>
            <span>{charCount} chars · {lineCount} lines{isDirty ? ' · Unsaved changes' : ''}</span>
          </div>
        </div>
        <div className="panel" data-testid="panel-analysis-preview">
          <div className="panel-head">
            <div className="panel-title"><Activity size={14} /> Analysis preview</div>
            <span className="panel-meta">
              {analysisStatus === 'ANALYZING'
                ? 'ANALYZING'
                : analysisStatus === 'ANALYZED'
                ? 'VERIFIED'
                : analysisStatus === 'STALE'
                ? 'STALE'
                : analysisStatus === 'ERROR'
                ? 'ERRORS'
                : 'LIVE SURFACE'}
            </span>
          </div>
          {analysisStatus === 'NO_ANALYSIS' && (
            <div style={{ padding: 20 }}>
              <EmptyState
                title="Source awaiting analysis"
                description="Click 'Analyze source' above to run the Lexer, Parser, and Assembler Pass-I pipeline."
                label="Awaiting analysis"
                icon={Activity}
              />
              <div style={{ textAlign: 'center', marginTop: 12 }}>
                <button
                  className="primary-button"
                  onClick={() => { void analyzeSource(); }}
                >
                  <FlaskConical size={13} /> Analyze source
                </button>
              </div>
            </div>
          )}
          {analysisStatus === 'ANALYZING' && (
            <EmptyState
              title="Analyzing source…"
              description="Running lexical analysis, syntax verification, and assembler Pass-I."
              label="ANALYZING"
              icon={Activity}
            />
          )}
          {analysisStatus === 'STALE' && (
            <div style={{ padding: 20 }}>
              <div className="waiting-chip" style={{ color: 'hsl(var(--accent))', marginBottom: 12 }}>
                <AlertTriangle size={11} style={{ marginRight: 4, display: 'inline' }} />
                ANALYSIS STALE
              </div>
              <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>Source code changed</h4>
              <p style={{ fontSize: 13, color: 'hsl(var(--muted-foreground))', lineHeight: 1.5, marginBottom: 16 }}>
                The source has been modified since the last analysis. Re-analyze to refresh tokens, symbol table, and intermediate code.
              </p>
              <button
                className="primary-button"
                onClick={() => { void analyzeSource(); }}
              >
                <FlaskConical size={13} /> Re-analyze source
              </button>
            </div>
          )}
          {analysisStatus === 'ERROR' && (
            <div style={{ padding: 16 }}>
              <div className="waiting-chip" style={{ color: 'hsl(var(--destructive))', marginBottom: 12 }}>
                <AlertTriangle size={11} style={{ marginRight: 4, display: 'inline' }} />
                COMPILER ERRORS ({diagnostics.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 280, overflowY: 'auto' }}>
                {diagnostics.map((d, i) => (
                  <div
                    key={i}
                    style={{
                      padding: '8px 10px',
                      background: 'hsl(var(--muted) / 0.3)',
                      borderRadius: 4,
                      font: '11px var(--app-font-mono)',
                      color: d.severity === 'ERROR' ? 'hsl(var(--destructive))' : 'hsl(var(--accent))',
                      borderLeft: `3px solid ${d.severity === 'ERROR' ? 'hsl(var(--destructive))' : 'hsl(var(--accent))'}`,
                    }}
                  >
                    [{d.severity}] {d.message}{d.line != null ? ` (line ${d.line}${d.column != null ? `:${d.column}` : ''})` : ''}
                  </div>
                ))}
              </div>
            </div>
          )}
          {analysisStatus === 'ANALYZED' && (
            <div style={{ padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                <span style={{ color: 'hsl(var(--primary))', font: '11px var(--app-font-mono)', fontWeight: 600 }}>
                  <CheckCircle2 size={13} style={{ marginRight: 4, display: 'inline' }} />
                  PASS-I COMPLETE
                </span>
                <span className="panel-meta">{analyzedResult?.final_location_counter != null ? `END LC: ${analyzedResult.final_location_counter}` : ''}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginBottom: 14 }}>
                <div style={{ padding: 10, background: 'hsl(var(--muted) / 0.3)', borderRadius: 4 }}>
                  <div style={{ fontSize: 10, color: 'hsl(var(--muted-foreground))', textTransform: 'uppercase' }}>Tokens</div>
                  <div style={{ fontSize: 16, fontWeight: 600, fontFamily: 'var(--app-font-mono)' }}>
                    {lexResult?.tokens.filter(t => t.type !== 'COMMENT').length ?? 0}
                  </div>
                </div>
                <div style={{ padding: 10, background: 'hsl(var(--muted) / 0.3)', borderRadius: 4 }}>
                  <div style={{ fontSize: 10, color: 'hsl(var(--muted-foreground))', textTransform: 'uppercase' }}>Statements</div>
                  <div style={{ fontSize: 16, fontWeight: 600, fontFamily: 'var(--app-font-mono)' }}>
                    {syntaxResult?.statements.length ?? 0}
                  </div>
                </div>
                <div style={{ padding: 10, background: 'hsl(var(--muted) / 0.3)', borderRadius: 4 }}>
                  <div style={{ fontSize: 10, color: 'hsl(var(--muted-foreground))', textTransform: 'uppercase' }}>Symbols</div>
                  <div style={{ fontSize: 16, fontWeight: 600, fontFamily: 'var(--app-font-mono)' }}>
                    {analyzedResult?.symbol_table.length ?? 0}
                  </div>
                </div>
                <div style={{ padding: 10, background: 'hsl(var(--muted) / 0.3)', borderRadius: 4 }}>
                  <div style={{ fontSize: 10, color: 'hsl(var(--muted-foreground))', textTransform: 'uppercase' }}>Literals / Pools</div>
                  <div style={{ fontSize: 16, fontWeight: 600, fontFamily: 'var(--app-font-mono)' }}>
                    {analyzedResult?.literal_table.length ?? 0} / {analyzedResult?.pool_table.length ?? 0}
                  </div>
                </div>
              </div>
              <div style={{ fontSize: 12, color: 'hsl(var(--muted-foreground))', lineHeight: 1.4 }}>
                Intermediate code: <strong style={{ color: 'hsl(var(--foreground))' }}>{analyzedResult?.intermediate_code.length ?? 0} records</strong>. Ready for Guided Lab or individual stage inspection.
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="home-notes">
        <div className="panel note-block" data-testid="panel-lab-principles">
          <h3><BookOpen size={15} /> What this lab makes visible</h3>
          <p>Every stage keeps its own representation. Nothing is silently collapsed between source and machine behavior.</p>
          <ul className="note-list">
            <li>Trace a source span into tokens, symbols, and intermediate records.</li>
            <li>Compare the hand-written representation with a future service response.</li>
            <li>Use the runtime surfaces only when verified memory and trace data exist.</li>
          </ul>
        </div>
        <div className="panel note-block" data-testid="panel-ready-state">
          <h3><Settings2 size={15} /> Service boundary</h3>
          <p>Client-side demo constants are isolated from view components. Connect a compiler API without changing this shell.</p>
          <div className="waiting-chip" style={{ marginTop: 14 }}>
            {analysisStatus === 'ANALYZED' ? 'PASS-I VERIFIED' : 'EXPLICIT PIPELINE ACTIVE'}
          </div>
        </div>
      </div>
    </>
  );
}

export function ExecutionPage({ source }: { source: string }) {
  const registerNames = ['AREG', 'BREG', 'CREG', 'DREG'];
  const conditionCodes = ['LT', 'LE', 'EQ', 'GT', 'GE', 'ANY'];
  return (
    <>
      <div className="page-intro">
        <div>
          <div className="eyebrow">Runtime / virtual machine</div>
          <h1 className="page-title" data-testid="heading-execution">Program Execution</h1>
          <p className="page-description">A debugger surface for the deterministic Educational Virtual Machine. It will never invent registers, memory, traces, or output.</p>
        </div>
        <span className="waiting-chip">VM NOT CONNECTED</span>
      </div>
      <div className="execution-layout" data-testid="execution-layout">
        <div className="panel execution-source" data-testid="panel-execution-source">
          <div className="panel-head"><div className="panel-title"><FileCode2 size={14} /> Source program</div><span className="panel-meta">READ ONLY</span></div>
          <pre className="execution-code">{source}</pre>
        </div>
        <div className="panel cpu-panel" data-testid="panel-vm-stage">
          <div className="panel-head"><div className="panel-title"><Cpu size={14} /> Virtual CPU</div><span className="panel-meta">WAITING</span></div>
          <div className="cpu-content">
            <div className="cpu-registers">
              <div className="cpu-major-row"><span>PC</span><strong>—</strong></div>
              {registerNames.map((register) => <div className="cpu-register-row" key={register}><span>{register}</span><strong>—</strong></div>)}
            </div>
            <div className="condition-block"><div className="debug-title"><span>Condition Code</span><span>WAITING</span></div><div className="condition-code">—</div><div className="condition-options">{conditionCodes.map((code) => <span key={code}>{code}</span>)}</div></div>
            <div className="cpu-meta-grid"><div><span>Current instruction</span><strong>—</strong></div><div><span>Execution status</span><strong>NOT CONNECTED</strong></div></div>
          </div>
        </div>
        <div className="panel memory-panel" data-testid="panel-execution-memory">
          <div className="panel-head"><div className="panel-title"><Database size={14} /> Memory</div><span className="panel-meta">NO MAP</span></div>
          <EmptyState title="Memory is waiting" description="Loaded memory cells will appear after the loader and execution engine return a verified state." label="Memory not connected yet" icon={Database} />
        </div>
        <div className="panel console-panel" data-testid="panel-program-output">
          <div className="panel-head"><div className="panel-title"><Terminal size={14} /> Program output</div><span className="panel-meta">CONSOLE</span></div>
          <div className="console-empty"><span className="console-cursor">&gt;</span><span>Waiting for program execution...</span></div>
        </div>
        <div className="execution-controls" data-testid="execution-controls">
          {([
            ['RUN', Play],
            ['PAUSE', Activity],
            ['STEP', ArrowRight],
            ['RESET', RotateCcw],
            ['STOP', X],
            ['RESTART', RotateCcw],
          ] as Array<[string, typeof Play]>).map(([label, Icon]) => <button className="ghost-button" disabled title="Execution engine not connected" key={label} data-testid={`button-execution-${label.toLowerCase()}`}><Icon size={13} /> {label}</button>)}
        </div>
        <div className="panel trace-panel" data-testid="panel-trace">
          <div className="panel-head"><div className="panel-title"><Table2 size={14} /> Execution trace</div><span className="panel-meta">NO EVENTS</span></div>
          <div className="trace-table-wrap">
            <table className="data-table trace-table"><thead><tr>{['Step', 'PC', 'Instruction', 'AREG', 'BREG', 'CREG', 'DREG', 'Condition Code', 'Memory Change', 'Output'].map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody><tr><td colSpan={10}>No execution trace exists yet. Trace rows will preserve instruction order, register changes, memory changes, and output.</td></tr></tbody></table>
          </div>
        </div>
        <div className="callout execution-integrity" data-testid="callout-runtime-integrity">
          <strong><ShieldIcon /> Integrity guard</strong>
          <p>Runtime controls stay disabled until an object-code artifact is supplied by the service layer.</p>
        </div>
      </div>
    </>
  );
}

function ShieldIcon() {
  return <span style={{ display: 'inline-flex', verticalAlign: 'middle', marginRight: 6 }}><Cable size={13} /></span>;
}

export function GuidedBar({ onExit, onReplay }: { onExit: () => void; onReplay: () => void }) {
  const [location, setLocation] = useLocation();
  const index = Math.max(0, labStages.findIndex((stage) => stage.path === location));
  const previous = labStages[Math.max(0, index - 1)];
  const next = labStages[Math.min(labStages.length - 1, index + 1)];
  const isFirst = index === 0;
  const isLast = index === labStages.length - 1;
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target;
      if (target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement || target instanceof HTMLSelectElement || (target instanceof HTMLElement && target.isContentEditable)) return;
      if ((event.key === 'ArrowLeft' || event.key.toLowerCase() === 'j') && !isFirst) {
        event.preventDefault();
        setLocation(previous.path);
      }
      if ((event.key === 'ArrowRight' || event.key === 'Enter' || event.key.toLowerCase() === 'k') && !isLast) {
        event.preventDefault();
        setLocation(next.path);
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        onExit();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isFirst, isLast, next.path, onExit, previous.path, setLocation]);
  return (
    <div className="guided-bar" data-testid="guided-bar">
      <div className="guided-copy"><strong>Guided lab · {String(index + 1).padStart(2, '0')} / {String(labStages.length).padStart(2, '0')}</strong><span>← Back · → Next · Enter Next · Esc Exit</span></div>
      <button className="guided-action" disabled={isFirst} onClick={() => setLocation(previous.path)} aria-label="Previous stage" data-testid="button-guided-back"><ArrowLeft size={14} /> Back</button>
      <button className="guided-action" disabled={isLast} onClick={() => setLocation(next.path)} aria-label="Next stage" data-testid="button-guided-next">Next <ArrowRight size={14} /></button>
      <button className="guided-action" onClick={onReplay} aria-label="Replay guided lab" data-testid="button-guided-replay"><RotateCcw size={14} /> Replay</button>
      <button className="guided-action" onClick={onExit} aria-label="Exit guided lab" data-testid="button-guided-exit"><X size={14} /> Exit</button>
    </div>
  );
}

export function GuidedControls({ onReplay }: { onReplay: () => void }) {
  return <button className="ghost-button" onClick={onReplay} data-testid="button-replay-lab"><RotateCcw size={13} /> Replay lab</button>;
}
