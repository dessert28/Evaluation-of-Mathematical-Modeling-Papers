import { useEffect, useState } from 'react'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Assets from './pages/Assets.jsx'
import Rubrics from './pages/Rubrics.jsx'
import Models from './pages/Models.jsx'
import CreateReview from './pages/CreateReview.jsx'
import ReviewTasks from './pages/ReviewTasks.jsx'
import ReviewDetail from './pages/ReviewDetail.jsx'
import History from './pages/History.jsx'

const routeTable = {
  '/overview': Dashboard,
  '/assets': Assets,
  '/rubrics': Rubrics,
  '/models': Models,
  '/create': CreateReview,
  '/tasks': ReviewTasks,
  '/history': History,
}

function currentPath() {
  const path = window.location.hash.replace(/^#/, '')
  return path || '/overview'
}

export function App() {
  const [path, setPath] = useState(currentPath)
  useEffect(() => {
    if (!window.location.hash) window.location.hash = '/overview'
    const update = () => setPath(currentPath())
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])

  const detailMatch = path.match(/^\/reviews\/([^/]+)$/)
  const Page = detailMatch ? ReviewDetail : (routeTable[path] || Dashboard)
  return (
    <Layout path={path}>
      <Page key={path} id={detailMatch?.[1]} />
    </Layout>
  )
}

export default App
