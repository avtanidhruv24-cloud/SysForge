/**
 * SysForge — Source text normalization and metrics calculation (Phase 5.1).
 *
 * Implements strict line and character counting rules:
 * - Line count: Normalizes CRLF and CR to LF. Empty string is 1 line.
 * - Character count: Total source characters EXCLUDING line terminators (\\r, \\n).
 */

export function normalizeSource(source: string): string {
  return source.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}

export function getLineCount(source: string): number {
  const normalized = normalizeSource(source);
  return normalized.length === 0 ? 1 : normalized.split('\n').length;
}

export function getCharacterCount(source: string): number {
  const normalized = normalizeSource(source);
  return normalized.replace(/\n/g, '').length;
}
