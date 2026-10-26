import Link from "next/link";
export default function NotFound() {
  return (
    <main className="legal">
      <Link href="/" className="brand">
        agentforge
      </Link>
      <h1>That skill took another path.</h1>
      <p>This page does not exist. The catalog is still here.</p>
      <Link className="primary" href="/">
        Find a skill
      </Link>
    </main>
  );
}
