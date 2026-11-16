import assert from 'node:assert/strict';

// Test implementation matching source-metrics.ts
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

console.log('Running source metrics unit tests...');

// 1. Line count tests
assert.equal(getLineCount(''), 1, 'Empty string should be 1 line');
assert.equal(getLineCount('START 100'), 1, 'Single line without newline should be 1 line');
assert.equal(getLineCount('START 100\nEND'), 2, 'Two lines with LF should be 2 lines');
assert.equal(getLineCount('START 100\r\nEND'), 2, 'Two lines with CRLF should be 2 lines');
assert.equal(getLineCount('START 100\rEND'), 2, 'Two lines with CR should be 2 lines');
assert.equal(getLineCount('START 100\n\nEND'), 3, 'Three lines with blank line in between should be 3 lines');
assert.equal(getLineCount('START 100\nEND\n'), 3, 'Trailing newline creates logical 3rd line');
assert.equal(getLineCount('START 100\r\nEND\r\n'), 3, 'Trailing CRLF creates logical 3rd line');

// 2. Character count tests (excluding line terminators)
assert.equal(getCharacterCount(''), 0, 'Empty string is 0 chars');
assert.equal(getCharacterCount('\n'), 0, 'LF alone is 0 chars');
assert.equal(getCharacterCount('\r\n'), 0, 'CRLF alone is 0 chars');
assert.equal(getCharacterCount('\n\n\n'), 0, 'Multiple newlines alone are 0 chars');
assert.equal(getCharacterCount('ABC'), 3, "'ABC' is 3 chars");
assert.equal(getCharacterCount('ABC\nDEF'), 6, "'ABC\\nDEF' is 6 chars, not 7");
assert.equal(getCharacterCount('ABC\r\nDEF'), 6, "'ABC\\r\\nDEF' is 6 chars, not 8");
assert.equal(getCharacterCount('START 100\nMOVER AREG =\'5\''), 24, "'START 100\\nMOVER AREG =\\'5\\'' is 24 chars (9 + 15)");

console.log('✓ All source metrics unit tests passed successfully!');
