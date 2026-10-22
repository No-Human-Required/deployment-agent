# Repository quality contract

## Repository grounding

Read the root README and the affected project's documentation and configuration. App Factory is a polyglot Nx monorepo: pnpm manages JavaScript/TypeScript, while Python tooling is introduced with actual Python projects. Do not infer an application stack from illustrative future projects or introduce empty scaffolding.

Preserve coherent project boundaries and capability-oriented package names. Applications remain private; pnpm workspace dependencies use `workspace:`. Follow existing affected-project conventions. Check actual package versions and scripts before specifying APIs or commands; a tool present in one package is not necessarily available repo-wide.

## Verification selection

Each slice states its acceptance evidence and narrow useful verification. Include failure cases that matter to changed behavior, compatibility, or integrity. Reuse existing harnesses; add tests when they prove behavior or guard meaningful regression. Do not add tests that merely mirror wording or implementation details.

There is no universal root build, test, or lint script. At the time this contract was introduced, existing verification includes:

```sh
pnpm --filter @app-factory/eslint-config lint
pnpm --filter @app-factory/eslint-config test
pnpm tools:lint
pnpm tools:typecheck
```

Use these for changes affecting that package or `tools/`, not as mandatory checks for every task. Confirm scripts still exist before execution. For new projects, establish appropriate verification alongside the project and record it in the prompt. Do not claim an unavailable check passed.

Choose evidence appropriate to the deliverable:

| Work | Useful evidence when applicable |
| --- | --- |
| UI behavior | Interaction, accessibility, state coverage, and visual inspection |
| API/integration | Contract examples, failure/access cases, consumer compatibility |
| Data/migration | Integrity invariants, representative existing data, resumability/recovery rehearsal |
| Infrastructure | Configuration validation, scoped dry run/plan, health and recovery criteria |
| Bug fix | Reproduction and regression evidence, relevant surrounding behavior |
| Performance | Comparable baseline and changed measurements under stated conditions |
| Research | Traceable sources, discriminating experiments, confidence and limitations |
| Documentation/workflow | Accurate examples, resolvable references, internally consistent lifecycle and realistic scenario walkthroughs |

## Execution and reporting

Keep edits within approved scope and preserve unrelated working-tree changes. Report artifacts changed, checks actually run, results, unrun checks with reasons, and downstream implications. Do not present recommendations as executed verification or hypotheses as findings.

Planning deployment, publishing, destructive migrations, or external writes does not authorize those actions. Describe required operational evidence and obtain any missing authorization at the action boundary. Ordinary local reversible edits and read-only investigation within the task do not require extra workflow gates.

Specialist guidance supplements this contract with relevant standards; it must not silently add scope or unsupported guarantees. Reconciliation checks actual outcomes before treating downstream dependencies as satisfied.
