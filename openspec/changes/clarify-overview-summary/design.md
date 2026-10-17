# Design

## Context

`summary` is a free-text string written by one model call (`overview/summary.py`), guarded for invented figures, then shown as the `PageHeader` lede. The model sees pseudonyms, not names; names are restored in the delivered text. The overview payload already has `client_rows` (id and name) for the UI. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Bold, linked client names and italic actions in the summary.
- Keep `summary` a string and the privacy model intact.

**Non-Goals:**
- Changing themes, ranking, or the actions list.
- General Markdown rendering of model text.

## Decisions

1. **Inline markup in the string, not a structured payload.** Two tokens only: `[[CL-0001]]` for a client and `_action text_` for the action to take. Alternative: change `summary` to a list of segments. Rejected: breaks the API/schema, persisted reports and the stub, for the same visible result.
2. **Clients referenced by id, name resolved in the UI.** The model never has to reproduce a name correctly, no pseudonym restore is needed for them, and the link target is unambiguous. The input payload gains `client_id` per action. Alternative: the model writes the (pseudonymised) name and the UI matches names; rejected as fragile.
3. **Guard.** Before the numeric check, client tokens are stripped (their digits are ids, not figures). Every token must name a client present in the actions given to the model; otherwise the summary is removed with a `guard_removed` gap, as for invented figures. Unbalanced `_` is not an error: the UI shows it literally.
4. **Tiny custom renderer, no Markdown library.** A function splits the string on the two tokens into React nodes (`<Link><strong>`, `<em>`). Anything else is plain text, so model output can never inject HTML or other formatting. A client id not in `client_rows` renders as the bare id, unlinked.
5. **Prompt.** Only the two or three most pressing actions (top of the list), each as client token, then the action in underscores, then a brief reason. Two to four sentences in total stays the limit; the summary never lists all actions.

## Risks / Trade-offs

- Model ignores the markup → summary shows as plain text, still correct; guard does not require tokens.
- Old persisted summaries have no markup → render plain until the runner is rerun.
- Underscores inside an action (e.g. snake_case words) could break the italic span → the prompt forbids them and the renderer only matches `_..._` on word boundaries.
