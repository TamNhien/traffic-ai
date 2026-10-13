/**
 * Show competition evidence whenever persisted AI/GT assignments overlap.
 * GT and AI totals are intentionally irrelevant: matching is temporal and
 * one-to-one, so either equal or unequal totals may hide competing candidates.
 * This helper is presentation-only and cannot alter the scoring report.
 */
export function shouldShowTemporalCompetitionReview(report, scoringAvailable) {
  if (!scoringAvailable || !report) return false
  const audit = report.temporal_assignment_audit
  return Number(audit?.missed_with_claimed_persisted_event || 0) > 0 ||
    Number(audit?.false_positives_near_assigned_ground_truth || 0) > 0
}
