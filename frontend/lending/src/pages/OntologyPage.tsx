import { useEffect, useState } from "react";
import { Alert, Collapse, Spin, Table, Typography } from "antd";
import { EXPLORER_URL, loadOntology, type OntologyPayload } from "../api";
import { ontologyReadout } from "../ontologyReadout";

function requiredLabel(value: boolean): string {
  return value ? "是" : "否";
}

export function OntologyPage() {
  const [schema, setSchema] = useState<OntologyPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    loadOntology()
      .then(setSchema)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "无法加载本体"));
  }, []);

  if (error) {
    return <Alert type="error" message={error} showIcon />;
  }
  if (!schema) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Spin tip="正在校验图谱…">
          <div style={{ minHeight: 48 }} />
        </Spin>
      </div>
    );
  }

  const readout = ontologyReadout(schema);

  return (
    <div className="page-wrap">
      <Typography.Title level={2}>贷款本体</Typography.Title>
      <Typography.Paragraph type="secondary">
        实例图在 Neo4j。lending schema 只在 <code>ontology/lending.json</code>
        。OWL/SHACL 是投影。可在{" "}
        <a href={EXPLORER_URL} target="_blank" rel="noreferrer">
          Explorer
        </a>{" "}
        的 Ontology Hub 加载 <code>ontology/lending.ttl</code>。
      </Typography.Paragraph>
      <Typography.Paragraph type="secondary">
        这套 schema 约束申请、文档和决策骨架，不驱动文档里的实体抽取。本页只读；改
        JSON 后需要重新加载 API 才会生效。
      </Typography.Paragraph>
      {readout.conforms ? (
        <Alert
          type="success"
          showIcon
          message={`当前图谱符合本体（检查了 ${readout.checked} 个节点）。`}
          description="校验读的是 lending.json 派生的必填字段和必填关系，不是对下方 Turtle 跑 SHACL。"
        />
      ) : (
        <Alert
          type="error"
          showIcon
          message="不符合本体"
          description={
            <ul>
              {readout.violations.map((item) => (
                <li key={item.key}>
                  <code>{item.id || "(no id)"}</code>
                  {item.type ? ` · ${item.type}` : ""}
                  {item.field ? (
                    <>
                      {" "}
                      · <code>{item.field}</code>
                    </>
                  ) : null}
                  {item.message ? ` — ${item.message}` : ""}
                </li>
              ))}
            </ul>
          }
        />
      )}
      <Typography.Title level={3} style={{ marginTop: 24 }}>
        本页检查的必填项
      </Typography.Title>
      <ul>
        {readout.requiredChecklist.map((item) => (
          <li key={item.key}>
            <code>{item.label}</code>
            {item.kind === "relationship" ? "（关系）" : "（属性）"}
          </li>
        ))}
      </ul>
      <Typography.Title level={3}>类</Typography.Title>
      <Table
        dataSource={readout.classes}
        pagination={false}
        columns={[
          { title: "名称", dataIndex: "name", render: (value: string) => <code>{value}</code> },
          { title: "说明", dataIndex: "description" },
        ]}
      />
      <Typography.Title level={3} style={{ marginTop: 24 }}>
        属性
      </Typography.Title>
      <Table
        dataSource={readout.properties}
        pagination={false}
        columns={[
          { title: "类", dataIndex: "domain" },
          { title: "属性", dataIndex: "name", render: (value: string) => <code>{value}</code> },
          { title: "必填", dataIndex: "required", render: requiredLabel },
          { title: "说明", dataIndex: "description" },
        ]}
      />
      <Typography.Title level={3} style={{ marginTop: 24 }}>
        关系
      </Typography.Title>
      <Table
        dataSource={readout.relationships}
        pagination={false}
        columns={[
          { title: "名称", dataIndex: "name", render: (value: string) => <code>{value}</code> },
          { title: "定义域", dataIndex: "domain" },
          { title: "值域", dataIndex: "range" },
          { title: "必填", dataIndex: "required", render: requiredLabel },
          { title: "说明", dataIndex: "description" },
        ]}
      />
      <Typography.Title level={3} style={{ marginTop: 24 }}>
        投影
      </Typography.Title>
      <Collapse
        items={[
          {
            key: "owl",
            label: "OWL",
            children: (
              <pre style={{ whiteSpace: "pre-wrap", background: "#f5f5f5", padding: 12 }}>
                {readout.owl}
              </pre>
            ),
          },
          {
            key: "shacl",
            label: "SHACL",
            children: (
              <pre style={{ whiteSpace: "pre-wrap", background: "#f5f5f5", padding: 12 }}>
                {readout.shacl}
              </pre>
            ),
          },
        ]}
      />
    </div>
  );
}
