# Question ID is frozen at first merge

The question ID is a hash of the normalized question text plus the sorted, normalized choices. The skill computes it once, when the question first enters the master bank, then stores it and never recomputes it. Every app tab (attempts, bookmarks, notes, spaced-repetition state) keys on this ID, so a typo fix or a Report re-check that edits the text must not change it.

## Consequences

- A row's ID can stop matching the hash of its current text. This is expected. Do not "repair" it.
- Dedupe compares the hash of an incoming question against both the stored IDs and the current-text hashes of existing rows.
- Sorting the choices before hashing makes a reordered copy of a question an exact duplicate.
