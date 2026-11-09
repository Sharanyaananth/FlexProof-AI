# FlexProof AI: Project Target

## Goal
Build an end-to-end system that helps an AI datacentre safely reduce its grid power when the grid asks, by using its battery and pausing flexible computing, while guaranteeing it can keep its promise and recover safely afterwards.

## What the system must do
- Decide how much power reduction can be safely promised to the grid.
- Prove the promise with at least 95% statistical reliability.
- Deliver the promise by re-planning every 5 minutes during the event.
- Verify that paused work catches up and the battery recharges without exceeding the grid limit.
- Work with real datacentre data, not only simulated data.

## Targets
1. Compare FlexProof against the chosen baseline (see `docs/research_notes.md`) on the same scenarios.
2. Replace simulated uncertainty with values learned from real public datasets.
3. Support multiple event durations (15, 30 and 60 minutes).
4. Build a real-time data connector and dashboard.
5. Test in shadow mode with real datacentre data.

## Success criteria
- Promise kept in at least 95% of unseen test scenarios.
- Recovery always stays within the grid limit.
- Clear, measurable improvement over the baseline in tight-recovery conditions.

## Timeline
About 3 to 4 months for the complete end-to-end system.