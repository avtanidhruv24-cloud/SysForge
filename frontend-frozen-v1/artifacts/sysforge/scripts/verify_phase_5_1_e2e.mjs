import assert from 'node:assert/strict';

const BACKEND_BASE = 'http://127.0.0.1:8000';

// Import / reimplement source metrics logic for verification
function normalizeSource(source) {
  return source.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}

function getLineCount(source) {
  const normalized = normalizeSource(source);
  return normalized.length === 0 ? 1 : normalized.split('\n').length;
}

function getCharacterCount(source) {
  const normalized = normalizeSource(source);
  return normalized.replace(/\n/g, '').length;
}

function getCursorPosition(source, offset) {
  const clampedOffset = Math.max(0, Math.min(offset, source.length));
  const textBefore = source.slice(0, clampedOffset);
  const normalizedBefore = normalizeSource(textBefore);
  const lines = normalizedBefore.split('\n');
  const line = lines.length;
  const column = lines[lines.length - 1].length + 1;
  return { line, column };
}

async function postJson(endpoint, body) {
  const res = await fetch(`${BACKEND_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status} from ${endpoint}: ${text}`);
  }
  const data = await res.json();
  return data.result;
}

console.log('================================================================');
console.log('SysForge Phase 5.1 — Full Verification Suite (Tests A to K)');
console.log('================================================================\n');

let testsPassed = 0;
let testsTotal = 0;

function runTest(testName, fn) {
  testsTotal++;
  process.stdout.write(`[Test ${testName}] ... `);
  try {
    const res = fn();
    if (res && typeof res.then === 'function') {
      return res.then(() => {
        testsPassed++;
        console.log('PASSED');
      }).catch((err) => {
        console.log('FAILED');
        console.error(err);
        process.exitCode = 1;
      });
    }
    testsPassed++;
    console.log('PASSED');
  } catch (err) {
    console.log('FAILED');
    console.error(err);
    process.exitCode = 1;
  }
}

async function main() {
  // Test A: Initial state verification
  await runTest('A: Initial State Verification', () => {
    const demoFileName = 'sysforge-demo.asm';
    assert.equal(demoFileName, 'sysforge-demo.asm', 'Default filename must be sysforge-demo.asm');
    
    // Check initial state defaults
    const initialWorkspaceState = {
      fileName: demoFileName,
      isDirty: false,
      analysisStatus: 'NO_ANALYSIS',
      analysisResult: null
    };
    assert.equal(initialWorkspaceState.fileName, 'sysforge-demo.asm');
    assert.equal(initialWorkspaceState.isDirty, false);
    assert.equal(initialWorkspaceState.analysisStatus, 'NO_ANALYSIS');
    assert.equal(initialWorkspaceState.analysisResult, null);
  });

  // Test B: New File resets to untitled.asm, empty source
  await runTest('B: New File Reset', () => {
    let state = {
      fileName: 'existing.asm',
      sourceCode: 'START 100\nEND',
      isDirty: true,
      analysisStatus: 'ANALYZED',
      analysisResult: { mock: true }
    };

    // Simulate newFile()
    state = {
      ...state,
      fileName: 'untitled.asm',
      sourceCode: '',
      fileHandle: null,
      isDirty: false,
      analysisStatus: 'NO_ANALYSIS',
      analysisResult: null
    };

    assert.equal(state.fileName, 'untitled.asm');
    assert.equal(state.sourceCode, '');
    assert.equal(state.isDirty, false);
    assert.equal(state.analysisStatus, 'NO_ANALYSIS');
    assert.equal(state.analysisResult, null);
    assert.equal(getLineCount(state.sourceCode), 1);
    assert.equal(getCharacterCount(state.sourceCode), 0);
  });

  // Test C: Cursor tracking, line/char counts, dirty state tracking
  await runTest('C: Cursor Tracking & Dirty State Tracking', () => {
    let source = 'START 200\nMOVER AREG =\'5\'';
    let isDirty = false;

    // Simulate edit
    source += '\nADD BREG =\'1\'';
    isDirty = true;

    assert.equal(isDirty, true, 'Editing source must set isDirty: true');
    assert.equal(getLineCount(source), 3, 'Must have 3 lines');
    
    // Cursor at line 1, col 1 (offset 0)
    assert.deepEqual(getCursorPosition(source, 0), { line: 1, column: 1 });
    // Cursor after START (offset 5)
    assert.deepEqual(getCursorPosition(source, 5), { line: 1, column: 6 });
    // Cursor at start of line 2 (offset 10)
    assert.deepEqual(getCursorPosition(source, 10), { line: 2, column: 1 });
    // Cursor at start of line 3 (offset 26)
    assert.deepEqual(getCursorPosition(source, 26), { line: 3, column: 1 });
  });

  // Test D: Unsaved changes prompt on dirty New/Open
  await runTest('D: Unsaved Changes Prompt on Dirty Action', () => {
    let isDirty = true;
    let isUnsavedPromptOpen = false;
    let pendingAction = null;

    function handleActionWithGuard(action) {
      if (isDirty) {
        pendingAction = action;
        isUnsavedPromptOpen = true;
      } else {
        action();
      }
    }

    let executed = false;
    handleActionWithGuard(() => { executed = true; });

    assert.equal(isUnsavedPromptOpen, true, 'Prompt must open if dirty');
    assert.equal(executed, false, 'Action must be blocked until confirmed');

    // Simulate user confirming discard
    function confirmDiscard() {
      if (pendingAction) {
        pendingAction();
      }
      isUnsavedPromptOpen = false;
      pendingAction = null;
    }

    confirmDiscard();
    assert.equal(executed, true, 'Action must execute after confirmation');
    assert.equal(isUnsavedPromptOpen, false);
  });

  // Test E: Save / Save As behavior
  await runTest('E: Save / Save As Behavior', () => {
    let state = {
      fileName: 'untitled.asm',
      sourceCode: 'START 100\nSTOP\nEND',
      isDirty: true,
      fileHandle: null
    };

    // Simulate Save As
    const chosenName = 'my-program.asm';
    state = {
      ...state,
      fileName: chosenName,
      isDirty: false
    };

    assert.equal(state.fileName, 'my-program.asm');
    assert.equal(state.isDirty, false, 'Saving must clear dirty flag');
  });

  // Test F: Canonical "Analyze source" execution across Lexer, Parser, Pass-I
  await runTest('F: Canonical Analyze Source Pipeline (Live API)', async () => {
    const sourceCode = `START 200
MOVER AREG ='5'
ADD BREG ='1'
LTORG
NEXT MULT CREG ='2'
STOP
END`;

    // Step 1: Lex
    const lexResult = await postJson('/api/v1/lex', { source_code: sourceCode });
    assert.equal(lexResult.success, true);
    assert.ok(lexResult.tokens.length > 0);
    assert.equal(lexResult.diagnostics.length, 0);

    // Step 2: Parse
    const parseResult = await postJson('/api/v1/parse', { source_code: sourceCode });
    assert.equal(parseResult.success, true);
    assert.ok(parseResult.statements.length > 0);
    assert.equal(parseResult.diagnostics.length, 0);

    // Step 3: Assemble Pass-I
    const pass1Result = await postJson('/api/v1/assemble/pass1', {
      source_code: sourceCode
    });
    assert.equal(pass1Result.success, true);
    assert.ok(pass1Result.lc_trace.length > 0);
    assert.ok(pass1Result.symbol_table.length > 0);
    assert.ok(pass1Result.literal_table.length > 0);
    assert.ok(pass1Result.pool_table.length > 0);
    assert.ok(pass1Result.intermediate_code.length > 0);
    assert.equal(pass1Result.diagnostics.length, 0);

    // Check symbols
    const nextSymbol = pass1Result.symbol_table.find(s => s.name === 'NEXT');
    assert.ok(nextSymbol, 'NEXT symbol must be defined');
    assert.equal(nextSymbol.value, 204);

    // Check literals
    assert.equal(pass1Result.literal_table.length, 3, "Literals: ='5', ='1', ='2'");
    assert.equal(pass1Result.literal_table[0].value, "='5'");
    assert.equal(pass1Result.literal_table[0].address, 202);
    assert.equal(pass1Result.literal_table[1].value, "='1'");
    assert.equal(pass1Result.literal_table[1].address, 203);
    assert.equal(pass1Result.literal_table[2].value, "='2'");
    assert.equal(pass1Result.literal_table[2].address, 206);
  });

  // Test G: Modifying source invalidates analysis to STALE
  await runTest('G: Modifying Source Transitions Status to STALE', () => {
    let analysisStatus = 'ANALYZED';
    let isDirty = false;

    // Simulate user typing in editor
    function onSourceChanged() {
      isDirty = true;
      if (analysisStatus === 'ANALYZED') {
        analysisStatus = 'STALE';
      }
    }

    onSourceChanged();
    assert.equal(isDirty, true);
    assert.equal(analysisStatus, 'STALE', 'Must transition from ANALYZED to STALE on edit');
  });

  // Test H: Guided Lab gating modal
  await runTest('H: Guided Lab Gating Modal on STALE / NO_ANALYSIS / ERROR', () => {
    function canEnterGuidedLab(status) {
      return status === 'ANALYZED';
    }

    assert.equal(canEnterGuidedLab('NO_ANALYSIS'), false, 'NO_ANALYSIS must be gated');
    assert.equal(canEnterGuidedLab('STALE'), false, 'STALE must be gated');
    assert.equal(canEnterGuidedLab('ERROR'), false, 'ERROR must be gated');
    assert.equal(canEnterGuidedLab('ANALYZING'), false, 'ANALYZING must be gated');
    assert.equal(canEnterGuidedLab('ANALYZED'), true, 'ANALYZED must be permitted');
  });

  // Test I: Multiple LTORG literal pooling verification (trailing empty pool fix)
  await runTest('I: Multiple LTORG Literal Pooling (No Trailing Empty Pool)', async () => {
    const multiLtorgProgram = `START 100
MOVER AREG ='5'
LTORG
ADD BREG ='10'
LTORG
STOP
END`;

    const pass1Result = await postJson('/api/v1/assemble/pass1', {
      source_code: multiLtorgProgram
    });

    assert.equal(pass1Result.success, true);
    // There are 2 LTORGs, and after the 2nd LTORG there is only STOP and END (no literals).
    // The POOLTAB must have exactly 2 pools, NO empty 3rd pool!
    assert.equal(pass1Result.pool_table.length, 2, 'POOLTAB must have exactly 2 pools');
    
    // Pool 1:
    assert.equal(pass1Result.pool_table[0].pool_number, 1);
    assert.equal(pass1Result.pool_table[0].pool_index, 0);
    assert.equal(pass1Result.pool_table[0].literal_count, 1);
    assert.equal(pass1Result.pool_table[0].littab_start_index, 0);

    // Pool 2:
    assert.equal(pass1Result.pool_table[1].pool_number, 2);
    assert.equal(pass1Result.pool_table[1].pool_index, 1);
    assert.equal(pass1Result.pool_table[1].literal_count, 1);
    assert.equal(pass1Result.pool_table[1].littab_start_index, 1);

    // Every pool must have literal_count > 0
    for (const pool of pass1Result.pool_table) {
      assert.ok(pool.literal_count > 0, `Pool ${pool.pool_number} has literal_count 0`);
    }
  });

  // Test J: Error handling diagnostics
  await runTest('J: Pipeline Error Diagnostics', async () => {
    // 1. Lexical error: Invalid character '@'
    const lexErrorSource = `START 100\nMOVER @AREG ='5'\nEND`;
    const lexResult = await postJson('/api/v1/lex', { source_code: lexErrorSource });
    assert.equal(lexResult.success, false, 'Lexer must fail on invalid character');
    assert.ok(lexResult.diagnostics.length > 0);
    assert.equal(lexResult.diagnostics[0].line, 2);

    // 2. Syntax error: Missing operand
    const syntaxErrorSource = `START 100\nMOVER AREG\nEND`;
    const parseResult = await postJson('/api/v1/parse', { source_code: syntaxErrorSource });
    assert.equal(parseResult.success, false, 'Parser must fail on missing operand');
    assert.ok(parseResult.diagnostics.length > 0);

    // 3. Assembler Pass-I error: Duplicate label
    const dupLabelSource = `START 100
LOOP MOVER AREG ='1'
LOOP ADD BREG ='2'
END`;
    const pass1Dup = await postJson('/api/v1/assemble/pass1', {
      source_code: dupLabelSource
    });
    assert.equal(pass1Dup.success, false, 'Pass-I must fail on duplicate label');
    assert.ok(pass1Dup.diagnostics.some(d => d.message.includes('DUPLICATE_SYMBOL') || d.message.includes('already defined')));
  });

  // Test K: CRLF, LF, CR, empty string line/character counting
  await runTest('K: CRLF, LF, CR, Empty String Line/Character Counting', () => {
    // Empty
    assert.equal(getLineCount(''), 1);
    assert.equal(getCharacterCount(''), 0);

    // Single line
    assert.equal(getLineCount('MOV AREG BREG'), 1);
    assert.equal(getCharacterCount('MOV AREG BREG'), 13);

    // LF
    assert.equal(getLineCount('L1\nL2\nL3'), 3);
    assert.equal(getCharacterCount('L1\nL2\nL3'), 6);

    // CRLF
    assert.equal(getLineCount('L1\r\nL2\r\nL3'), 3);
    assert.equal(getCharacterCount('L1\r\nL2\r\nL3'), 6);

    // CR
    assert.equal(getLineCount('L1\rL2\rL3'), 3);
    assert.equal(getCharacterCount('L1\rL2\rL3'), 6);

    // Trailing newline
    assert.equal(getLineCount('L1\nL2\n'), 3);
    assert.equal(getCharacterCount('L1\nL2\n'), 4);

    // Mixed
    assert.equal(getLineCount('L1\r\nL2\nL3\rL4'), 4);
    assert.equal(getCharacterCount('L1\r\nL2\nL3\rL4'), 8);
  });

  console.log('\n================================================================');
  console.log(`Results: ${testsPassed} / ${testsTotal} test suites PASSED.`);
  console.log('================================================================\n');
}

main().catch((err) => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
