import Link from "next/link";
export default function Terms() {
  return (
    <main className="legal">
      <Link href="/" className="brand">
        agentforge
      </Link>
      <h1>Using AgentForge</h1>
      <p>
        AgentForge is an early service for discovering public agent skills.
        Listings describe upstream resources and link to their original authors.
      </p>
      <h2>Review before adoption</h2>
      <p>
        A listing is not a security review, endorsement, or guarantee of
        compatibility. Inspect a skill and its supporting scripts, permissions,
        credentials, and license before using it. The service does not authorize
        an agent to install or execute a package on your behalf.
      </p>
      <h2>Sources and licenses</h2>
      <p>
        Third party skills keep their own licenses. Unknown license information
        is shown as unknown. The public AgentForge skill and CLI have their own
        Apache 2.0 license. Original platform code, website code, and design are
        proprietary, with all rights reserved.
      </p>
      <h2>Availability</h2>
      <p>
        Catalog coverage and retrieval quality are still being evaluated. The
        service can return incomplete results or become unavailable. Automated
        bulk scraping and attempts to bypass request limits are not supported.
      </p>
      <a href="https://github.com/agentforge-hq/company">Project information</a>
      <p>
        <Link href="/">Back to search</Link>
      </p>
    </main>
  );
}
