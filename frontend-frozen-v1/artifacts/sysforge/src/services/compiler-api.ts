// ============================================================================
// SysForge compiler API client
//
// This module is the ONLY place in the frontend that calls the FastAPI
// backend.  All components must use these exports — no raw fetch() calls
// in React components.
//
// Phase 3: analyze() and getStage() connected to real backend.
// Phase 4.5: Added typed LexerResult / SyntaxResult + lex() / parse().
// ============================================================================

// ---------------------------------------------------------------------------
// Stage union type
// ---------------------------------------------------------------------------

export type AnalysisStage =
  | 'lexical'
  | 'syntax'
  | 'macro'
  | 'pass-one'
  | 'tables'
  | 'intermediate'
  | 'pass-two'
  | 'object-code'
  | 'linker'
  | 'loader'
  | 'memory'
  | 'ai'
  | 'execution';

// ---------------------------------------------------------------------------
// Shared primitive types (mirror backend Pydantic models)
// ---------------------------------------------------------------------------

export type SourceSpan = {
  line: number;
  column: number;
  length: number;
};

// ---------------------------------------------------------------------------
// Lexer types — mirrors backend LexerResult / Token
// ---------------------------------------------------------------------------

export type TokenType =
  | 'DIRECTIVE'
  | 'IMPERATIVE'
  | 'DECLARATIVE'
  | 'REGISTER'
  | 'CONDITION_CODE'
  | 'SYMBOL'
  | 'NUMBER'
  | 'LITERAL'
  | 'COMMENT'
  | 'NEWLINE'
  | 'EOF'
  | 'UNKNOWN';

export type Token = {
  type: TokenType;
  value: string;
  line: number;
  column: number;
  span: SourceSpan | null;
};

export type LexDiagnostic = {
  stage: string;
  severity: 'ERROR' | 'WARNING' | 'INFO';
  code: string;
  message: string;
  line: number | null;
  column: number | null;
  token_value: string | null;
};

export type LexerResult = {
  tokens: Token[];
  diagnostics: LexDiagnostic[];
  success: boolean;
  token_count: number;
};

export type LexResponse = {
  session_id: string;
  status: 'COMPLETED' | 'ERROR' | 'NOT_IMPLEMENTED' | 'NOT_STARTED' | 'IN_PROGRESS';
  result: LexerResult | null;
};

// ---------------------------------------------------------------------------
// Parser types — mirrors backend SyntaxResult / ParsedStatement
// ---------------------------------------------------------------------------

export type SyntaxError = {
  message: string;
  line: number | null;
  column: number | null;
  token_value: string | null;
  expected: string | null;
};

export type StatementClass = 'IS' | 'DL' | 'AD';

export type ParsedStatement = {
  line_number: number;
  label: string | null;
  directive: string | null;
  imperative: string | null;
  declarative: string | null;
  register: string | null;
  condition_code: string | null;
  operand: string | null;
  statement_class: StatementClass | null;
  tokens: Token[];
  span: SourceSpan | null;
  is_valid: boolean;
  errors: SyntaxError[];
};

export type ParseDiagnostic = {
  stage: string;
  severity: 'ERROR' | 'WARNING' | 'INFO';
  code: string;
  message: string;
  line: number | null;
  column: number | null;
  token_value: string | null;
};

export type SyntaxResult = {
  statements: ParsedStatement[];
  diagnostics: ParseDiagnostic[];
  success: boolean;
  statement_count: number;
};

export type ParseResponse = {
  session_id: string;
  status: 'COMPLETED' | 'ERROR' | 'NOT_IMPLEMENTED' | 'NOT_STARTED' | 'IN_PROGRESS';
  result: SyntaxResult | null;
};

// ---------------------------------------------------------------------------
// Assembler Pass-I types — mirrors backend Pass1Result
// ---------------------------------------------------------------------------

export type SymbolTableEntry = {
  name: string;
  value: number;
  defined_at_line: number | null;
  is_defined: boolean;
  references: number[];
  index: number | null;
  forward_reference: boolean;
  status: string;
};

export type LiteralTableEntry = {
  value: string;
  numeric_value: number | null;
  pool_index: number;
  address: number | null;
  width: number;
  index?: number | null;
  references?: number[];
};

export type PoolTableEntry = {
  pool_index: number;
  pool_number: number;
  littab_start_index: number;
  literal_count: number;
  ltorg_line: number | null;
  trigger: string | null;
  ending_literal_index?: number | null;
};

export type OperandField = {
  type: string;
  value: string;
  name?: string | null;
  index?: number | null;
};

export type IntermediateRecord = {
  source_line: number;
  location_counter: number | null;
  statement_class: string;
  opcode_value: number | null;
  mnemonic: string;
  operands: OperandField[];
  label?: string | null;
};

export type LCTraceEntry = {
  source_line: number;
  statement: string;
  lc_before: number | null;
  action: string;
  lc_after: number | null;
  explanation?: string | null;
};

export type Pass1Diagnostic = {
  stage: string;
  severity: 'ERROR' | 'WARNING' | 'INFO';
  code: string;
  message: string;
  line: number | null;
  column: number | null;
  token_value: string | null;
};

export type Pass1Result = {
  symbol_table: SymbolTableEntry[];
  literal_table: LiteralTableEntry[];
  pool_table: PoolTableEntry[];
  intermediate_code: IntermediateRecord[];
  starting_address: number | null;
  final_location_counter: number | null;
  lc_trace: LCTraceEntry[];
  processed_statement_count: number;
  unresolved_symbol_count: number;
  literal_count: number;
  pool_count: number;
  diagnostics: Pass1Diagnostic[];
  success: boolean;
};

export type Pass1Response = {
  session_id: string;
  status: 'COMPLETED' | 'ERROR' | 'NOT_IMPLEMENTED' | 'NOT_STARTED' | 'IN_PROGRESS';
  result: Pass1Result | null;
};

// ---------------------------------------------------------------------------
// Full-pipeline types (used by analyze())
// ---------------------------------------------------------------------------

export type AnalysisRequest = {
  sourceCode: string;
  stages?: AnalysisStage[];
};

export type AnalysisResponse = {
  sessionId: string;
  sourceCode: string;
  completedStages: AnalysisStage[];
  results: Partial<Record<AnalysisStage, unknown>>;
};

export type CompilerApi = {
  analyze(request: AnalysisRequest): Promise<AnalysisResponse>;
  getStage(sessionId: string, stage: AnalysisStage): Promise<unknown>;
  /** Run the lexer only. Returns the raw LexResponse from the backend. */
  lex(sourceCode: string): Promise<LexResponse>;
  /** Run the lexer + parser. Returns the raw ParseResponse from the backend. */
  parse(sourceCode: string): Promise<ParseResponse>;
  /** Run Assembler Pass-I. Returns the raw Pass1Response from the backend. */
  assemblePass1(sourceCode: string): Promise<Pass1Response>;
};

// ---------------------------------------------------------------------------
// Configuration — reads VITE_API_BASE_URL from .env
// ---------------------------------------------------------------------------

/** Base URL of the FastAPI backend.  Reads VITE_API_BASE_URL from .env. */
const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000';

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`SysForge API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`SysForge API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Response adaptors
// ---------------------------------------------------------------------------

/** Map FastAPI snake_case response → frontend camelCase AnalysisResponse. */
function adaptAnalysisResponse(raw: Record<string, unknown>): AnalysisResponse {
  return {
    sessionId: raw['session_id'] as string,
    sourceCode: raw['source_code'] as string,
    completedStages: (raw['completed_stages'] as string[]) as AnalysisStage[],
    results: (raw['results'] as Partial<Record<AnalysisStage, unknown>>) ?? {},
  };
}

// ---------------------------------------------------------------------------
// Exported API singleton
// The UI depends on this boundary — never add fetch() calls to components.
// ---------------------------------------------------------------------------

export const compilerApi: CompilerApi = {
  // Full pipeline
  async analyze(request: AnalysisRequest): Promise<AnalysisResponse> {
    const raw = await postJson<Record<string, unknown>>('/api/v1/analyze', {
      source_code: request.sourceCode,
      stages: request.stages ?? null,
    });
    return adaptAnalysisResponse(raw);
  },

  async getStage(sessionId: string, stage: AnalysisStage): Promise<unknown> {
    return getJson<unknown>(`/api/v1/session/${sessionId}/${stage}`);
  },

  // Lexer only
  async lex(sourceCode: string): Promise<LexResponse> {
    return postJson<LexResponse>('/api/v1/lex', { source_code: sourceCode });
  },

  // Lexer + parser
  async parse(sourceCode: string): Promise<ParseResponse> {
    return postJson<ParseResponse>('/api/v1/parse', { source_code: sourceCode });
  },

  // Assembler Pass-I
  async assemblePass1(sourceCode: string): Promise<Pass1Response> {
    return postJson<Pass1Response>('/api/v1/assemble/pass1', { source_code: sourceCode });
  },
};
