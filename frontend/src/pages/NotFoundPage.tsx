import { Link } from "react-router-dom"
import { EmptyState } from "../components/Feedback"
import { SearchIcon } from "../components/Icons"

export function NotFoundPage() {
  return (
    <div className="container page">
      <EmptyState
        icon={<SearchIcon size={24} />}
        title="This page doesn't exist"
        action={
          <Link to="/" className="btn btn-primary">
            Browse flights
          </Link>
        }
      >
        The link may be old or mistyped. Everything you can book starts from the flight list.
      </EmptyState>
    </div>
  )
}
