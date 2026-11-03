/**
 * Reads the clap-times box: blank is null (find the claps from the audio);
 * otherwise one number of seconds per chosen video, camera 0 first. Pure, so
 * the tests use it too.
 *
 * Commas, semicolons and spaces all separate, and empty pieces are dropped, so
 * a stray comma ("1.25, 0.80,") is one time short rather than a clap at 0 s.
 * Each time is a plain decimal with a point: JavaScript's Number would also
 * take 0x10, 1e2 or +1, which no video player shows.
 */
const PLAIN_SECONDS = /^(\d+(\.\d*)?|\.\d+)$/
const DECIMAL_COMMA_HINT = 'Commas separate the times; use a point for decimals (1.25, not 1,25).'

export function parseClapTimes(text: string, videos: number): number[] | null | string {
  const trimmed = text.trim()
  if (!trimmed) return null
  // "1,5 2,5" is two times written with decimal commas, not four times
  const decimalCommas = /\d,\d/.test(trimmed) && !trimmed.includes('.')
  if (decimalCommas && /\s/.test(trimmed)) return DECIMAL_COMMA_HINT
  const pieces = trimmed.split(/[\s,;]+/).filter(Boolean)
  if (pieces.some((p) => !PLAIN_SECONDS.test(p))) return 'Clap times must be numbers of seconds, e.g. 1.25 0.80 1.10'
  const times = pieces.map(Number)
  if (times.length !== videos) {
    const hint = /\d,\d/.test(trimmed) ? ` ${DECIMAL_COMMA_HINT}` : ''
    return `Give ${videos} clap times, one per video in camera order (got ${times.length}).${hint}`
  }
  return times
}
