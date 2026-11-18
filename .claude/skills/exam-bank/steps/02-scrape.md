# Scrape

A script step with no subagent. It opens a headed browser window for each Curated site with pages left, except `certsafari`, whose answers sit in the static HTML and which is fetched over plain HTTP with no window.

1. Tell the user a browser window opens for sites that need one (ExamTopics), and that they log in or solve any challenge there themselves. Never type credentials or solve a CAPTCHA.
2. Start `python .claude/skills/exam-bank/scripts/eb.py scrape <exam>` as a background command and wait for it to exit. Do not poll it.
3. Report its output. A line `waiting on user: <action>` means the window stayed open for 8 minutes with no question cards. Tell the user the action, and that rerunning the command continues from the last saved page.
4. A line `paywall at page N` means the site's free limit ended the source. Pages before N are saved, the source counts as done, and the scrape step moves on. Tell the user, and carry on with the next step. A rerun probes page N once more, in case the account's limit changed.
