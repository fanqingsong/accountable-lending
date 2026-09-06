import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { App } from "./App";
import { ChatPage } from "./pages/ChatPage";
import { ImportPage } from "./pages/ImportPage";
import { OntologyPage } from "./pages/OntologyPage";
import { RetrievePage } from "./pages/RetrievePage";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ConfigProvider locale={zhCN}>
      <BrowserRouter basename="/lending">
        <Routes>
          <Route element={<App />}>
            <Route index element={<ImportPage />} />
            <Route path="retrieve" element={<RetrievePage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="ontology" element={<OntologyPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  </StrictMode>,
);
