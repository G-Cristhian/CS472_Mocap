/**
 * Reads the clap-times box: blank is null (find the claps from the audio);
 * otherwise one number of seconds per chosen video, camera 0 first. Pure, so
 * the tests use it too.
 *
 * Commas, semicolons and spaces all separate, and empty pieces are dropped, so
 * a stray comma ("1.25, 0.80,") is one time short rather than a clap at 0 s.
 */
export function parseClapTimes(text: string, videos: number): number[] | null | string {
  const trimmed = text.trim()
  if (!trimmed) return null
  const times = trimmed
    .split(/[\s,;]+/)
    .filter(Boolean)
    .map(Number)
  if (times.some((t) => !isFinite(t) || t < 0)) return 'Clap times must be numbers of seconds, e.g. 1.25 0.80 1.10'
  if (times.length !== videos) return `Give ${videos} clap times, one per video in camera order (got ${times.length}).`
  return times
}
