import Link from "next/link";
export default function Privacy() {
  return (
    <main className="legal">
      <Link href="/" className="brand">
        agentforge
      </Link>
      <h1>Privacy</h1>
      <p>
        AgentForge is an early skill discovery service. This page describes the
        current implementation.
      </p>
      <h2>Search requests</h2>
      <p>
        The website and installed skill send a task query, an optional harness
        name, a result limit, and any tool names or setup/account preferences
        you explicitly provide to the AgentForge service. We do not need the
        accounts or keys themselves. Searches run against
        a catalog stored in Pixeltable Cloud. A small embedding model processes
        the query on that backend. Search does not require an account.
      </p>
      <p>
        The application does not intentionally store raw search queries, upload
        repository files, or collect entire conversations. Do not include
        passwords, private documents, or other sensitive material in a query.
      </p>
      <h2>Hosting and sources</h2>
      <p>
        Vercel hosts the website and its public API. Pixeltable Cloud hosts the
        catalog and search backend. These providers process technical request
        information needed to serve and secure requests. Public skill sources
        and revisions are linked in the results.
      </p>
      <h2>Browser storage and analytics</h2>
      <p>
        The application does not add advertising trackers or analytics cookies.
        Search and category choices stay in the current page state. Hosting
        infrastructure may retain its own technical logs.
      </p>
      <h2>Contact</h2>
      <p>
        For questions or a listing removal request, use the company repository.
        Do not post private information in a public issue.
      </p>
      <a href="https://github.com/agentforge-hq/company">
        AgentForge company repository
      </a>
      <p>
        <Link href="/">Back to search</Link>
      </p>
    </main>
  );
}
