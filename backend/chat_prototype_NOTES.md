# Chat UI prototype

Question: What should the agent conversation interface look like, given that
the model only writes a sentence from graph evidence?

Three variants were tried on `/lending/chat?variant=`.

- **A — 审计台**: conversation left, persistent evidence right. Primary move is inspect.
- **B — 带出处对话**: linear chat; citations expand under each answer. Primary move is talk.
- **C — 案件简报**: no bubbles; one structured dossier per question. Primary move is interrogate a case file.

Verdict: **A — 审计台** is the product chat page (`frontend/lending/src/pages/ChatPage.tsx`).
The switcher is gone ([ADR-0007](../docs/adr/0007-react-antd-lending-ui.md)).
