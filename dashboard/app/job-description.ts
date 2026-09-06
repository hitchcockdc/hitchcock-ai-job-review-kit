const ENTITY_PATTERN = /&(?:#x[\da-f]+|#\d+|nbsp|amp|lt|gt|quot|apos);/gi;

function decodeEntity(entity: string) {
  const normalized = entity.toLowerCase();
  const named: Record<string, string> = {
    '&nbsp;': ' ',
    '&amp;': '&',
    '&lt;': '<',
    '&gt;': '>',
    '&quot;': '"',
    '&apos;': "'",
  };
  if (named[normalized] !== undefined) return named[normalized];

  const hexadecimal = normalized.startsWith('&#x');
  const codePoint = Number.parseInt(
    normalized.slice(hexadecimal ? 3 : 2, -1),
    hexadecimal ? 16 : 10,
  );
  if (!Number.isFinite(codePoint) || codePoint < 0 || codePoint > 0x10ffff) {
    return entity;
  }
  return String.fromCodePoint(codePoint);
}

function decodeEntities(value: string) {
  let decoded = value;
  for (let pass = 0; pass < 3; pass += 1) {
    const next = decoded.replace(ENTITY_PATTERN, decodeEntity);
    if (next === decoded) break;
    decoded = next;
  }
  return decoded;
}

export function cleanJobDescription(value: string) {
  const decoded = decodeEntities(value);
  return decoded
    .replace(/\\+(?=<\/?[a-z][^>]*>)/gi, '')
    .replace(/<(?:br|hr)\s*\/?\s*>/gi, '\n')
    .replace(/<\/(?:p|div|li|h[1-6]|section|article)>/gi, '\n')
    .replace(/<li(?:\s[^>]*)?>/gi, '• ')
    .replace(/<[^>]*>/g, ' ')
    .replace(/[\t\f\v ]+/g, ' ')
    .replace(/ *\n */g, '\n')
    .replace(/\n{2,}/g, '\n')
    .trim();
}

export function jobDescriptionSummary(value: string) {
  return (cleanJobDescription(value).match(/[^.!?]+[.!?]+|[^.!?]+$/g) ?? [])
    .slice(0, 3)
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();
}
