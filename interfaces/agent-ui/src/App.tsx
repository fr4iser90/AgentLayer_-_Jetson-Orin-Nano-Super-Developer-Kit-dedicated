import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { SettingsLayout } from "./layout/SettingsLayout";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAdmin } from "./auth/RequireAdmin";
import { RequireSession } from "./auth/RequireSession";
import { AppLayout } from "./layout/AppLayout";
import { AdminLayout } from "./layout/AdminLayout";
import { AdminDashboard } from "./pages/admin/AdminDashboard";
import { AdminInterfaces } from "./pages/admin/AdminInterfaces";
import { AdminTools } from "./pages/admin/AdminTools";
import { AdminUsers } from "./pages/admin/AdminUsers";
import { AdminScheduledJobs } from "./pages/admin/AdminScheduledJobs";
import { ChatPage } from "./pages/ChatPage";
import { DocsPage } from "./pages/DocsPage";
import { HomePage } from "./pages/HomePage";
import { AgentSettings } from "./pages/settings/AgentSettings";
import { ConnectionsSettings } from "./pages/settings/ConnectionsSettings";
import { ProfileSettings } from "./pages/settings/ProfileSettings";
import { ToolsSettings } from "./pages/settings/ToolsSettings";
import { AdminIdeAgent } from "./pages/admin/AdminIdeAgent";
import { StudioPage } from "./pages/StudioPage";
import { IdeAgentPage } from "./pages/IdeAgentPage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { LoginPage } from "./pages/LoginPage";

export function App() {
  return (
    <BrowserRouter basename="/app">
      <AuthProvider>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="login" element={<LoginPage />} />
          <Route element={<RequireSession />}>
            <Route path="/" element={<HomePage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="ide-agent" element={<IdeAgentPage />} />
            <Route path="studio" element={<StudioPage />} />
            <Route path="workspace" element={<WorkspacePage />} />
            <Route path="docs" element={<DocsPage />} />
            <Route path="settings" element={<SettingsLayout />}>
              <Route index element={<Navigate to="/settings/profile" replace />} />
              <Route path="profile" element={<ProfileSettings />} />
              <Route path="connections" element={<ConnectionsSettings />} />
              <Route path="tools" element={<ToolsSettings />} />
              <Route path="agent" element={<AgentSettings />} />
              <Route path="experimental" element={<Navigate to="/admin/ide-agent" replace />} />
            </Route>
            <Route path="admin" element={<RequireAdmin />}>
              <Route element={<AdminLayout />}>
                <Route index element={<AdminDashboard />} />
                <Route path="interfaces" element={<AdminInterfaces />} />
                <Route path="discord" element={<Navigate to="../interfaces" replace />} />
                <Route path="telegram" element={<Navigate to="../interfaces" replace />} />
                <Route path="tools" element={<AdminTools />} />
                <Route path="users" element={<AdminUsers />} />
                <Route path="scheduled-jobs" element={<AdminScheduledJobs />} />
                <Route path="ide-agent" element={<AdminIdeAgent />} />
                <Route path="workflows" element={<Navigate to="../scheduled-jobs" replace />} />
              </Route>
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
