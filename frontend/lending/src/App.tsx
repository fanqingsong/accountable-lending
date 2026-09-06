import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Layout, Menu, Typography } from "antd";
import { EXPLORER_URL } from "./api";

const items = [
  { key: "/", label: <NavLink to="/">导入</NavLink> },
  { key: "/retrieve", label: <NavLink to="/retrieve">检索</NavLink> },
  { key: "/chat", label: <NavLink to="/chat">问答</NavLink> },
  { key: "/ontology", label: <NavLink to="/ontology">本体</NavLink> },
];

export function App() {
  const location = useLocation();
  const isChat = location.pathname === "/chat";

  return (
    <Layout style={{ minHeight: "100%" }}>
      <Layout.Header style={{ display: "flex", alignItems: "center", gap: 24, paddingInline: 20 }}>
        <Typography.Text style={{ color: "#fff", fontWeight: 600, whiteSpace: "nowrap" }}>
          Accountable Lending
        </Typography.Text>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[isChat ? "/chat" : location.pathname]}
          items={items}
          style={{ flex: 1, minWidth: 0 }}
        />
        <a href={EXPLORER_URL} style={{ color: "#fff", whiteSpace: "nowrap" }}>
          知识图谱
        </a>
      </Layout.Header>
      <Layout.Content style={isChat ? undefined : { padding: "24px 20px 48px" }}>
        <Outlet />
      </Layout.Content>
    </Layout>
  );
}
