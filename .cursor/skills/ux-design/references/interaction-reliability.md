# Interaction reliability

Use this guidance for stateful experiences where timing or interruption can change what a user sees or believes happened.

## State and user control

Distinguish user intent, local draft, submitted work, and confirmed durable state. Identify which state drives visible feedback and which actions remain available at each transition. Determine how edits, navigation, reloads, or another actor's changes interact with pending work where relevant.

For optimistic behavior, establish what is reversible, how failure is shown, and how newer user edits survive rollback. For repeated or competing actions, define duplicate suppression or replacement behavior and how stale responses are prevented from overwriting current intent. Do not specify a technical state mechanism before agreeing on observable behavior.

## Interruption and recovery

Define recovery from partial failure, lost connectivity, expired permission, or unknown submission outcomes when they affect this journey. Preserve useful user input where appropriate. Distinguish retrying an operation from checking whether it already succeeded; the interface must not promise safe retries without contract support.

Focus, selection, scroll position, and keyboard context are part of continuity. Establish what happens when content disappears, dialogs close, errors appear, or async results replace a region. Dynamic announcements should convey useful state changes without repeatedly interrupting users. Avoid unnecessary reflow or motion that obscures the active task.

## AI-assisted experiences

Distinguish generated suggestions from accepted edits and external actions. Make partial output, uncertainty, editing, rejection, and regeneration behavior understandable where relevant. Define whether stopping generation also stops downstream work; do not imply cancellation or undo can reverse effects that already occurred. Preserve user changes when generated content updates. Do not display invented confidence or imply source verification that has not happened.

## Evidence to seek

Select journeys that could expose broken user expectations: rapid repeated action, navigation during submission, a failed optimistic change after another edit, delayed stale results, keyboard-only recovery, or interruption during generation. Evaluate observable behavior and preservation of work, not just rendered labels. Keep validation scoped to the change and report limits of automated accessibility or simulated timing checks.
