import type { CausedLink, Decision } from "../api";
import { CATEGORY_LABEL, OUTCOME_LABEL, labelOf } from "../labels";

type Props = {
  decisions?: Decision[];
  caused?: CausedLink[];
  focusId?: string;
};

export function DecisionChain({ decisions = [], caused = [], focusId }: Props) {
  return (
    <div className="decision-chain">
      {decisions.length === 0 ? (
        <p className="evidence-meta">这次没有决策节点。</p>
      ) : (
        decisions.map((item, index) => (
          <div
            key={`${item.category}-${index}`}
            className={`decision-step${focusId === `d-${index}` ? " hl" : ""}`}
          >
            <strong>
              {labelOf(CATEGORY_LABEL, item.category)} → {labelOf(OUTCOME_LABEL, item.outcome)}
            </strong>
            <p>{item.reasoning || item.scenario || ""}</p>
          </div>
        ))
      )}
      {caused.length > 0 ? (
        <ul className="caused-list">
          {caused.map((link, index) => (
            <li key={`${link.from}-${link.to}-${index}`}>
              <code>{link.from}</code> CAUSED <code>{link.to}</code>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
