import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAdmin } from "./auth/RequireAdmin";
import { RequireSession } from "./auth/RequireSession";
import { AppLayout } from "./layout/AppLayout";
import { AdminDashboard } from "./pages/admin/AdminDashboard";
import { AdminInterfaces } from "./pages/admin/AdminInterfaces";
import { AdminTools } from "./pages/admin/AdminTools";
import { AdminUsers } from "./pages/admin/AdminUsers";
import { AdminWorkflows } from "./pages/admin/AdminWorkflows";
import { ChatPage } from "./pages/ChatPage";
import { HomePage } from "./pages/HomePage";
import { StudioPage } from "./pages/StudioPage";

export function App() {
  return (
    <BrowserRouter basename="/app">
      <AuthProvider>
      <Routes>
        <Route element={<AppLayout />}>
          <Route element={<RequireSession />}>
            <Route path="/" element={<HomePage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="studio" element={<StudioPage />} />
            <Route path="admin" element={<RequireAdmin />}>
              <Route index element={<AdminDashboard />} />
              <Route path="interfaces" element={<AdminInterfaces />} />
              <Route path="tools" element={<AdminTools />} />
              <Route path="users" element={<AdminUsers />} />
              <Route path="workflows" element={<AdminWorkflows />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
