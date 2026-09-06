import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Alert, Button, Checkbox, Form, Input, Table, Typography, Upload } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import type { UploadFile } from "antd/es/upload/interface";
import { EXPLORER_URL, importApplication, listApplications, type ApplicationRow } from "../api";

const ACCEPT = ".txt,.pdf,.docx,.md";

type FormValues = {
  applicant_name: string;
  application_id?: string;
  high_risk?: boolean;
  thin_credit?: boolean;
};

export function ImportPage() {
  const [form] = Form.useForm<FormValues>();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [apps, setApps] = useState<ApplicationRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: ReactNode } | null>(
    null,
  );

  function loadApps() {
    return listApplications()
      .then(setApps)
      .catch(() => setApps([]));
  }

  useEffect(() => {
    void loadApps();
  }, []);

  async function onFinish(values: FormValues) {
    if (!fileList.length) {
      setMessage({ type: "error", text: "请选择申请材料。" });
      return;
    }
    const data = new FormData();
    data.append("applicant_name", values.applicant_name);
    data.append("application_id", values.application_id || "");
    if (values.high_risk) data.append("high_risk", "on");
    if (values.thin_credit) data.append("thin_credit", "on");
    for (const item of fileList) {
      if (item.originFileObj) data.append("files", item.originFileObj);
    }
    setLoading(true);
    setMessage(null);
    try {
      const body = await importApplication(data);
      const count = Array.isArray(body.decisions)
        ? body.decisions.length
        : Object.keys(body.decisions || {}).length;
      setMessage({
        type: "success",
        text: (
          <>
            已导入 <strong>{body.applicant_name}</strong> (<code>{body.application_id}</code>)，
            {body.entity_count} 个实体，{count} 条决策。{" "}
            <a href={EXPLORER_URL}>打开知识图谱</a> · <Link to="/retrieve">图谱检索</Link>
          </>
        ),
      });
      form.resetFields();
      setFileList([]);
      await loadApps();
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "导入失败" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-wrap">
      <Typography.Title level={2}>导入贷款申请</Typography.Title>
      <Typography.Paragraph type="secondary">
        上传 TXT / PDF / DOCX。每个申请会写成独立的 Application 节点，实体 id 带案件前缀，不会和已有案件合并。
      </Typography.Paragraph>
      {message ? <Alert type={message.type} message={message.text} showIcon style={{ marginBottom: 16 }} /> : null}
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Form.Item name="applicant_name" label="申请人名称" rules={[{ required: true, message: "必填" }]}>
          <Input placeholder="Harbor Bakehouse Pvt Ltd" />
        </Form.Item>
        <Form.Item name="application_id" label="案件 ID（可空，默认由名称生成）">
          <Input placeholder="harbor-bakery" />
        </Form.Item>
        <Form.Item label="申请材料" required>
          <Upload.Dragger
            multiple
            accept={ACCEPT}
            fileList={fileList}
            beforeUpload={() => false}
            onChange={(info) => setFileList(info.fileList)}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p>点击或拖入文件（.txt / .pdf / .docx / .md）</p>
          </Upload.Dragger>
        </Form.Item>
        <Form.Item name="high_risk" valuePropName="checked">
          <Checkbox>高风险（收入集中 / 风险备忘）</Checkbox>
        </Form.Item>
        <Form.Item name="thin_credit" valuePropName="checked">
          <Checkbox>信贷记录薄（无银行还款记录）</Checkbox>
        </Form.Item>
        <Typography.Paragraph type="secondary">
          两项都勾选时，规则会推出 RequiresManualReview，并转人工审；否则记录为通过。
        </Typography.Paragraph>
        <Button type="primary" htmlType="submit" loading={loading}>
          导入并写入图谱
        </Button>
      </Form>
      <Typography.Title level={3} style={{ marginTop: 32 }}>
        已有案件
      </Typography.Title>
      <Table
        rowKey={(row) => String(row.application_id || row.id)}
        dataSource={apps}
        pagination={false}
        locale={{ emptyText: "还没有案件。" }}
        columns={[
          { title: "application_id", dataIndex: "application_id", render: (value, row) => <code>{value || row.id}</code> },
          { title: "名称", dataIndex: "name" },
        ]}
      />
    </div>
  );
}
