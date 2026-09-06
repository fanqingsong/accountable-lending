import { useState } from "react";
import { Alert, Button, Form, Input, Typography } from "antd";
import { retrieveQuery, type RetrievePayload } from "../api";
import { DecisionChain } from "../components/DecisionChain";
import { EvidenceBlocks } from "../components/EvidenceBlocks";

export function RetrievePage() {
  const [payload, setPayload] = useState<RetrievePayload | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onFinish(values: { query: string }) {
    setLoading(true);
    setError("");
    try {
      setPayload(await retrieveQuery(values.query.trim()));
    } catch (err) {
      setPayload(null);
      setError(err instanceof Error ? err.message : "检索失败");
    } finally {
      setLoading(false);
    }
  }

  const empty =
    payload &&
    !(payload.chunks || []).length &&
    !(payload.decisions || []).length &&
    !(payload.caused || []).length &&
    !(payload.entities || []).length;

  return (
    <div className="page-wrap">
      <Typography.Title level={2}>图谱检索</Typography.Title>
      <Typography.Paragraph type="secondary">
        无 LLM。返回文档片段、相关实体，以及决策的 CAUSED 链。
      </Typography.Paragraph>
      <Form layout="vertical" onFinish={onFinish} initialValues={{ query: "Sunrise 为什么转人工审？" }}>
        <Form.Item name="query" label="问题" rules={[{ required: true, message: "请输入问题" }]}>
          <Input />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={loading}>
          检索
        </Button>
      </Form>
      {error ? <Alert type="error" message={error} showIcon style={{ marginTop: 16 }} /> : null}
      {payload?.query ? (
        <div style={{ marginTop: 24 }}>
          <Typography.Title level={3}>检索结果</Typography.Title>
          {empty ? (
            <Typography.Paragraph type="secondary">
              没有命中。试着带上申请人名称，或问「为什么转人工」。
            </Typography.Paragraph>
          ) : (
            <>
              <Typography.Title level={4}>决策链</Typography.Title>
              <DecisionChain decisions={payload.decisions} caused={payload.caused} />
              <EvidenceBlocks chunks={payload.chunks} entities={payload.entities} />
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
