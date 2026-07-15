import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { AboutPage } from './routes/AboutPage'
import { BacktestPage } from './routes/BacktestPage'
import { CompanyPage } from './routes/CompanyPage'
import { DashboardPage } from './routes/DashboardPage'
import { ExplorerPage } from './routes/ExplorerPage'
import { FilingPage } from './routes/FilingPage'
import { MaterialPage } from './routes/MaterialPage'
import { NotFoundPage } from './routes/NotFoundPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="materials/:materialId" element={<MaterialPage />} />
          <Route path="companies/:ticker" element={<CompanyPage />} />
          <Route path="filings/:extractionId" element={<FilingPage />} />
          <Route path="explorer" element={<ExplorerPage />} />
          <Route path="backtest" element={<BacktestPage />} />
          <Route path="about" element={<AboutPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
