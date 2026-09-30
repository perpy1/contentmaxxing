# Capture

Read the capture skill. Save the supplied text/file with `capture <file>` using
an appropriate kind and the user's sharing/consent restrictions. If the source
is spoken in this chat, preserve the creator's exact words in a labeled text
file; never invent source text. Report what was captured and its location.
Mine it as well when the user asks for ideas; otherwise suggest mining next.

If `progress` identifies a saved follow-up question, inspect that idea's
`development.gaps`. Capture the supplied answer, then use the compound skill's
`ideas resolve` contract to attach exact evidence and explain how it answers the
gap. Preserve unanswered questions; capturing a file alone does not resolve them.
