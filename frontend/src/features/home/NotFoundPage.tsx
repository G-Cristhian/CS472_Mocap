import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="page">
      <h1 className="page-title">This screen does not exist yet</h1>
      <p className="page-sub">
        The prototype covers Dashboard, Record, Projects, a project workspace, Recordings and
        Settings.
      </p>
      <p style={{ marginTop: 24 }}>
        <Link className="btn btn--primary" to="/">
          Back to home
        </Link>
      </p>
    </div>
  )
}
