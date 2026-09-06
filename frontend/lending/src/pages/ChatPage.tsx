import { useState } from "react";
import { Button, Input, Space, Typography } from "antd";
import { chatQuery, type ChatPayload } from "../api";
import { DecisionChain } from "../components/DecisionChain";
import { EvidenceBlocks } from "../components/EvidenceBlocks";
import { CATEGORY_LABEL, labelOf, sourceLabel } from "../labels";

type UserTurn = { role: "user"; text: string };
type AssistantTurn = { role: "assistant"; payload?: ChatPayload; pending?: boolean };
type Turn = UserTurn | AssistantTurn;

export function ChatPage() {
  const [query, setQuery] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [pending, setPending] = useState(false);
  const [focus, setFocus] = useState("");

  const latest = [...turns].reverse().find(
    (item): item is AssistantTurn => item.role === "assistant" && Boolean(item.payload),
  );
  const evidence = latest?.payload;

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || pending) return;
    setPending(true);
    setFocus("");
    setTurns((prev) => [...prev, { role: "user", text: trimmed }, { role: "assistant", pending: true }]);
    setQuery("");
    try {
      const payload = await chatQuery(trimmed);
      setTurns((prev) => {
        const next = prev.slice(0, -1);
        next.push({ role: "assistant", payload });
        return next;
      });
    } catch (err) {
      setTurns((prev) => {
        const next = prev.slice(0, -1);
        next.push({
          role: "assistant",
          payload: {
            answer: "请求失败：" + (err instanceof Error ? err.message : ""),
            source: "extractive",
            decisions: [],
            chunks: [],
            entities: [],
          },
        });
        return next;
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="audit-desk">
      <section className="audit-thread">
        <div className="audit-log">
          {turns.length === 0 ? (
            <p className="evidence-meta">把问题写在下面。右侧是卷宗，不是聊天记录。模型只写句子，不改图谱。</p>
          ) : (
            turns.map((turn, index) => {
              if (turn.role === "user") {
                return (
                  <div key={index} className="audit-turn">
                    <div className="audit-q">问</div>
                    <div className="audit-a">{turn.text}</div>
                  </div>
                );
              }
              if (turn.pending) {
                return (
                  <div key={index} className="audit-turn evidence-meta">
                    正在从图谱取证…
                  </div>
                );
              }
              const cites = [
                ...(turn.payload?.decisions || []).map((item, i) => ({
                  id: `d-${i}`,
                  kind: "决策",
                  label: labelOf(CATEGORY_LABEL, item.category),
                })),
                ...(turn.payload?.chunks || []).map((item, i) => ({
                  id: `c-${i}`,
                  kind: "材料",
                  label: `${item.kind || "Document"} · ${item.application_id || ""}`,
                })),
              ];
              return (
                <div key={index} className="audit-turn">
                  <div className="audit-q">
                    {sourceLabel(turn.payload?.source, turn.payload?.generation_error)}
                  </div>
                  <div className="audit-a">{turn.payload?.answer}</div>
                  <Space wrap style={{ marginTop: 8 }}>
                    {cites.map((item) => (
                      <Button
                        key={item.id}
                        size="small"
                        type={focus === item.id ? "primary" : "default"}
                        onClick={() => setFocus(item.id)}
                      >
                        {item.kind} {item.label}
                      </Button>
                    ))}
                  </Space>
                </div>
              );
            })
          )}
        </div>
        <form
          className="audit-composer"
          onSubmit={(event) => {
            event.preventDefault();
            void ask(query);
          }}
        >
          <Input.TextArea
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            disabled={pending}
            placeholder="Sunrise 为什么转人工审？"
            autoSize={{ minRows: 2, maxRows: 6 }}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void ask(query);
              }
            }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
            <Typography.Text type="secondary">Enter 发送 · 证据始终在右</Typography.Text>
            <Button type="primary" htmlType="submit" loading={pending}>
              取证并回答
            </Button>
          </div>
        </form>
      </section>
      <aside className="audit-panel">
        {evidence ? (
          <>
            <div className="evidence-meta">
              {sourceLabel(evidence.source, evidence.generation_error)}
            </div>
            <Typography.Title level={4}>决策链</Typography.Title>
            <DecisionChain decisions={evidence.decisions} caused={evidence.caused} focusId={focus} />
            <EvidenceBlocks chunks={evidence.chunks} entities={evidence.entities} focusId={focus} />
          </>
        ) : (
          <p className="evidence-meta">
            左侧提问后，这次回答用到的决策链、材料和实体会钉在这里。模型只写句子，不改图谱。
          </p>
        )}
      </aside>
    </div>
  );
}
