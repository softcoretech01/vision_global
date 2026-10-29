import { Routes, Route, Navigate } from 'react-router-dom'
import { useStore } from './store/useStore.jsx'
import Login from './components/Login.jsx'
import Layout from './components/Layout.jsx'
import { Toast } from './components/ui.jsx'
import Dashboard from './pages/Dashboard.jsx'
import BuyerEnquiry from './pages/BuyerEnquiry.jsx'
import SupplierProposal from './pages/SupplierProposal.jsx'
import SupplierProposalDetail from './pages/SupplierProposalDetail.jsx'
import BuyerQuotation, { BuyerTabPage } from './pages/BuyerQuotation.jsx'
import Administration from './pages/Administration.jsx'

export default function App() {
  const { auth } = useStore()
  if (!auth) return (<><Login /><Toast /></>)

  return (
    <>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/buyer-enquiry" element={<BuyerEnquiry />} />
          <Route path="/supplier-proposal" element={<SupplierProposal />} />
          <Route path="/supplier-proposal/:id" element={<SupplierProposalDetail />} />
          <Route path="/buyer-quotation" element={<BuyerQuotation />} />
          <Route path="/potential" element={<BuyerTabPage tab="potential" />} />
          <Route path="/need-support" element={<BuyerTabPage tab="support" />} />
          <Route path="/administration" element={<Navigate to="/administration/users" replace />} />
          <Route path="/administration/:section" element={<Administration />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
      <Toast />
    </>
  )
}
