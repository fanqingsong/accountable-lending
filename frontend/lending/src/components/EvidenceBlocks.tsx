import type { Chunk, EntityHit } from "../api";

type Props = {
  chunks?: Chunk[];
  entities?: EntityHit[];
  focusId?: string;
};

export function EvidenceBlocks({ chunks = [], entities = [], focusId }: Props) {
  return (
    <div>
      <h3>材料</h3>
      {chunks.length === 0 ? (
        <p className="evidence-meta">没有命中材料。</p>
      ) : (
        chunks.map((item, index) => (
          <div
            key={`${item.application_id}-${index}`}
            className={`evidence-block${focusId === `c-${index}` ? " hl" : ""}`}
          >
            <div className="evidence-meta">
              {item.kind} · {item.application_id}
              {item.score != null ? ` · score ${item.score}` : ""} · {item.source || "keyword"}
            </div>
            <div>{item.text}</div>
          </div>
        ))
      )}
      <h3>实体</h3>
      {entities.length === 0 ? (
        <p className="evidence-meta">没有相关实体。</p>
      ) : (
        entities.map((item, index) => (
          <div key={`${item.text}-${index}`} className="evidence-block">
            {item.text} <span className="evidence-meta">[{item.type}]</span>
          </div>
        ))
      )}
    </div>
  );
}
