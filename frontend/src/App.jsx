import { createRoot } from "react-dom/client";
import DashboardPage from "./pages/DashboardPage.jsx";
import "./styles/app.css";

function App() {
  return <DashboardPage />;
}

createRoot(document.getElementById("root")).render(<App />);
