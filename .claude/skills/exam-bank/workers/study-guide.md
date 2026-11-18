# Study guide chapter

Read the input file named in the prompt. Write one Markdown chapter to its `chapter_path`, the final path. Read only this worker file and that input for bank content. Reply with one line: `<subdomain> done`.

Use every fed question to identify the concepts this Subdomain tests. `active_ids` lists the whole Subdomain; `questions` is the fed sample. Cite only IDs from `questions`. Rows with `marked: true` have an Uncertain answer or low confidence. No claim may rest only on marked rows. Support such a claim with an unmarked row or fetched Google Cloud documentation, or omit it.

Write YAML front matter with these fields:

- `exam`, `subdomain`, `title`, `guide_version`, `model`: copy the input strings exactly. Quote `subdomain` and `guide_version`.
- `question_ids`: every fed question ID, in input order.
- `written_at`: copy the input's UTC `written_at` timestamp for this run as a quoted string.

Write 1,500 to 3,000 words, with these six level-two headings in this order:

1. Scope. Explain what the Subdomain covers.
2. Key concepts. For each service explain what it is, when to pick it, limits, and the closest alternative.
3. Decision table. Include scenario cue, choice, and why.
4. Traps. Explain common wrong decisions and the distinction that resolves each.
5. Question map. Link concepts to fed question IDs.
6. References. Link only documentation pages fetched during this session.

Paraphrase every scenario. Teach concepts and cite IDs instead of reproducing questions or choices. The script rejects any shared run of 12 words from an input stem or choice. It also rejects missing or wrong front matter, missing or reordered headings, unknown cited IDs, invalid URLs, and chapters outside 1,200 to 3,500 words.

Use model knowledge and, as needed, WebSearch and WebFetch restricted to Google Cloud documentation. A link passes only with HTTPS and host `cloud.google.com` or a host ending in `.cloud.google.com`. Include links only to pages you fetched in this session. Write only the chapter. The script owns the index and bank files.
