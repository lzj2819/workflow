export function containsUnresolvedUnknown(text) {
  const withoutQuotedProtocolValues = String(text)
    .replace(/[“"]UNKNOWN[”"]/gu, '')
    .replace(/'UNKNOWN'/gu, '')
  return /\bUNKNOWN\b/u.test(withoutQuotedProtocolValues)
}
