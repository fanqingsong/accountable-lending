import type { OntologyPayload } from "./api";

const SCHEMA_DESCRIPTION: Record<string, string> = {
  Application: "一笔贷款申请（案件）",
  Decision: "已记录的决策结果，须有类别和结论",
  Document: "已摄入的申请人文件",
  Entity: "从文档抽出的参与者或事实，不是申请、文档或决策",
  application_id: "稳定的申请标识",
  category: "决策类别",
  outcome: "决策结果",
  HAS_DECISION: "把决策挂到申请上；不能代替 CAUSED，也不是审计轨迹",
  HAS_DOCUMENT: "把文档挂到申请上",
  CAUSED: "决策到决策的因果边；审计轨迹沿这条边上溯",
};

export function schemaDescription(name?: string, fallback?: string): string {
  if (name && SCHEMA_DESCRIPTION[name]) {
    return SCHEMA_DESCRIPTION[name];
  }
  return fallback || "";
}

export type ClassRow = {
  key: string;
  name: string;
  description: string;
};

export type PropertyRow = {
  key: string;
  domain: string;
  name: string;
  range: string;
  required: boolean;
  description: string;
};

export type RelationshipRow = {
  key: string;
  name: string;
  domain: string;
  range: string;
  required: boolean;
  description: string;
};

export type RequiredItem = {
  key: string;
  kind: "property" | "relationship";
  label: string;
};

export type ViolationRow = {
  key: string;
  id: string;
  type: string;
  field: string;
  message: string;
};

export type OntologyReadout = {
  classes: ClassRow[];
  properties: PropertyRow[];
  relationships: RelationshipRow[];
  requiredChecklist: RequiredItem[];
  violations: ViolationRow[];
  conforms: boolean;
  checked: number | string;
  owl: string;
  shacl: string;
};

export function ontologyReadout(payload: OntologyPayload | null | undefined): OntologyReadout {
  const ontology = payload?.ontology || {};
  const classes = (ontology.classes || []).map((item, index) => {
    const name = item.name || "";
    return {
      key: `${name}-${index}`,
      name,
      description: schemaDescription(name, item.description),
    };
  });
  const properties = (ontology.properties || []).map((item, index) => {
    const name = item.name || "";
    return {
      key: `${item.domain}-${name}-${index}`,
      domain: item.domain || "",
      name,
      range: item.range || "",
      required: Boolean(item.required),
      description: schemaDescription(name, item.description),
    };
  });
  const relationships = (ontology.relationships || []).map((item, index) => {
    const name = item.name || "";
    return {
      key: `${item.domain}-${name}-${index}`,
      name,
      domain: item.domain || "",
      range: item.range || "",
      required: Boolean(item.required),
      description: schemaDescription(name, item.description),
    };
  });
  const requiredChecklist: RequiredItem[] = [
    ...properties
      .filter((item) => item.required && item.name)
      .map((item) => ({
        key: `prop-${item.key}`,
        kind: "property" as const,
        label: `${item.domain}.${item.name}`,
      })),
    ...relationships
      .filter((item) => item.required && item.name)
      .map((item) => ({
        key: `rel-${item.key}`,
        kind: "relationship" as const,
        label: item.name,
      })),
  ];
  const violations = (payload?.validation?.violations || []).map((item, index) => ({
    key: `${item.id}-${item.field}-${index}`,
    id: item.id || "",
    type: item.type || "",
    field: item.field || "",
    message: item.message || "",
  }));
  return {
    classes,
    properties,
    relationships,
    requiredChecklist,
    violations,
    conforms: Boolean(payload?.validation?.conforms),
    checked: payload?.validation?.checked ?? 0,
    owl: payload?.owl || "",
    shacl: payload?.shacl || "",
  };
}
