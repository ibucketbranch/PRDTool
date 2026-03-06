export default function Home() {
  return (
    <main className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Organizer Dashboard</h1>
      <p className="text-neutral-600 mb-8">
        Visual interface to view file statistics, search documents, and manage your document organization.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <DashboardCard
          title="Statistics"
          description="View file type counts and category distributions"
          href="/statistics"
        />
        <DashboardCard
          title="Search"
          description="Search documents using natural language queries"
          href="/search"
        />
        <DashboardCard
          title="Browse"
          description="Browse all documents with filtering and sorting"
          href="/browse"
        />
        <DashboardCard
          title="Empty Folders"
          description="Manage empty folders after consolidation"
          href="/empty-folders"
        />
        <DashboardCard
          title="File Health"
          description="File health score, duplicates, and storage savings"
          href="/health"
        />
        <DashboardCard
          title="Duplicate Files"
          description="Scan for exact duplicate files by hash"
          href="/dedup"
        />
        <DashboardCard
          title="Inbox Processor"
          description="Process new files from In-Box folder"
          href="/inbox"
        />
        <DashboardCard
          title="Scatter Report"
          description="View files in wrong taxonomy bins and propose corrections"
          href="/scatter-report"
        />
        <DashboardCard
          title="Agents"
          description="View agent status and trigger manual cycles"
          href="/agents"
        />
      </div>
    </main>
  );
}

function DashboardCard({
  title,
  description,
  href,
}: {
  title: string;
  description: string;
  href: string;
}) {
  return (
    <a
      href={href}
      className="block p-6 bg-neutral-50 rounded-lg border border-neutral-200 hover:border-neutral-300 hover:bg-neutral-100 transition-colors"
    >
      <h2 className="text-xl font-semibold mb-2">{title}</h2>
      <p className="text-neutral-600">{description}</p>
    </a>
  );
}
