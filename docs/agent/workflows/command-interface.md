# Repository command interface

Shared invocation rules for repository commands that explicitly list this file in their `docs` frontmatter. Each such command has an **Interface** section with Purpose, Usage, Input, Options, Examples, and Command-specific errors. That section is the source for its help response; do not maintain a separate help script or duplicate help text elsewhere.

## Interpret the invocation

- Treat the command name, option tokens, and at most one documented positional input as a chat invocation, not a shell command. A command may also have an implicit input source such as the Git index. Do not run shell expansion or interpret the input as executable code.
- A valueless option is written `--name`. An option with a value is written `--name=value`; its command must document the accepted values. Options may precede or follow the input. `--` ends option recognition, so later text is input even if it begins with `--`.
- A command may accept free text, a path, a Cursor file/folder reference, none of these, or a subset. Its Input table documents both positional and implicit inputs. Treat quoted paths with spaces as one positional input. Do not guess that arbitrary prose is a path. Reject positional input when the command documents no positional argument; an implicit source does not make a positional argument valid.
- If optional positional input is omitted, use the command's documented default first, or a target already unambiguous in this conversation. If neither applies and a target is needed, ask for it as described below. Do not select an arbitrary folder from a repository scan. Resolve an implicit input from its documented source; if that source is empty, follow the command-specific error response instead of asking for a substitute positional value.

## Recover missing input or option values

For a required input or valued option whose value is missing (including `--name=` with an empty value), ask for one missing item at a time before task work or state changes. Validate the answer against the command's Input or Options table. If the user cancels or declines, stop without changes; never invent a value. These rules recover command invocation values; they do not prescribe tools for later requirement or decision discussions.

- When there are concrete valid values to choose from, present them through `AskQuestion`. Rank choices by relevance to the current conversation, then by recent use or modification, with a stable name tie-breaker. Show at most the top **10 candidate values**. Permit a free-text choice for an unlisted value when the tool supports it; if explicit `Other` or `Cancel` controls consume option slots, reduce the candidate count so at most 10 choices are displayed in total.
- When the value is open-ended, or no concrete valid choices can be discovered, ask the developer in chat to type the value and wait for their reply. Do not use `AskQuestion` with placeholder choices such as “I will type it in Other” or “I will paste a path in Other.”
- A supplied value that is invalid is not silently replaced by the first choice. Explain the constraint and ask again using concrete choices or a direct chat request for text, unless the user cancels.

## Help and errors

When recognized as an option, `--help` takes precedence over all other tokens. Text after the `--` separator remains literal input. Show the command's purpose, usage, positional and implicit inputs with their sources and empty behavior, options with defaults and persistence, and examples from its Interface section. Then stop. Do not inspect task state, ask a workflow question, run checks, or change files.

For an unknown option, a value on a valueless option, conflicting options, excess input, or an unsupported input kind, state the specific problem, show the Usage line and a pointer to `--help`, and stop without side effects. Recover a missing required input or missing value for a known valued option through concrete `AskQuestion` choices or a direct chat request as above. A command-specific missing resource or ineligible state follows that command's error table. Keep errors concise and do not begin the workflow before the invocation is valid.
