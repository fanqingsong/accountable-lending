export const CATEGORY_LABEL: Record<string, string> = {
  risk_classification: "风险分类",
  policy_check: "政策核验",
  final_decision: "最终结论",
};

export const OUTCOME_LABEL: Record<string, string> = {
  high_risk: "高风险",
  standard_risk: "标准风险",
  manual_review_required: "需人工审",
  policy_cleared: "政策通过",
  referred_to_manual_review: "转人工审",
  approved: "通过",
};

export function labelOf(map: Record<string, string>, key?: string): string {
  if (!key) return "—";
  return map[key] || key;
}

export function sourceLabel(source?: string): string {
  return source === "ollama" ? "Ollama 成文" : "图谱摘录 · 未调用模型";
}
