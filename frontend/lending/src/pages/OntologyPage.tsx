import { useEffect, useState } from "react";
import { Alert, Spin, Table, Typography } from "antd";
import { loadOntology, type OntologyPayload } from "../api";

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

  const report = schema.validation || {};
  const rows = (schema.ontology?.properties || []).map((prop, index) => ({
    key: `${prop.domain}-${prop.name}-${index}`,
    ...prop,
  }));

  return (
    <div className="page-wrap">
      <Typography.Title level={2}>贷款本体</Typography.Title>
      <Typography.Paragraph type="secondary">
        实例图在 Neo4j。OWL/SHACL 是 schema。可在 Explorer 的 Ontology Hub 加载{" "}
        <code>ontology/lending.ttl</code>。
      </Typography.Paragraph>
      {report.conforms ? (
        <Alert type="success" showIcon message={`当前图谱符合本体（检查了 ${report.checked} 个节点）。`} />
      ) : (
        <Alert
          type="error"
          showIcon
          message="不符合本体"
          description={
            <ul>
              {(report.violations || []).map((item) => (
                <li key={item.id}>
                  <code>{item.id}</code> — {item.message}
                </li>
              ))}
            </ul>
          }
        />
      )}
      <Typography.Title level={3} style={{ marginTop: 24 }}>
        必填字段
      </Typography.Title>
      <Table
        dataSource={rows}
        pagination={false}
        columns={[
          { title: "类", dataIndex: "domain" },
          { title: "属性", dataIndex: "name", render: (value: string) => <code>{value}</code> },
          { title: "必填", dataIndex: "required", render: (value: boolean) => (value ? "是" : "否") },
          { title: "说明", dataIndex: "description" },
        ]}
      />
      <Typography.Title level={3}>SHACL</Typography.Title>
      <Typography.Paragraph>
        <pre style={{ whiteSpace: "pre-wrap", background: "#f5f5f5", padding: 12 }}>{schema.shacl || ""}</pre>
      </Typography.Paragraph>
    </div>
  );
}
