# PRDTool: The Product Story

## The Problem

Every person and every business drowns in files.

Not because they create too many -- because nobody organizes them after creation.
Files arrive from email, downloads, shared drives, scanned documents, phone backups,
cloud sync, and a dozen other sources. Each one lands wherever is convenient in the
moment. Over months and years, the mess compounds.

The industry's answer has been "just search for it." Gmail trained a generation to
believe that organization is unnecessary if search is good enough. But search fails
in specific, predictable ways:

- You search "insurance" and get 300 results. Which one is the current policy?
- You search "contract" but the file was named `MSA_draft_v3_final_MV.docx`.
- You search for something you forgot exists. Search cannot help with what you
  do not know to look for.
- You search "tax 2024" but the accountant named it `1040_Valderrama_amended.pdf`.

Search requires you to already know what you are looking for. That is not
intelligence. That is a lookup table.

Meanwhile, people "fix as they go" -- renaming a file here, moving a folder there --
each fix introducing a new inconsistency. Monday the file is `insurance.pdf`. By
March it is `Auto_Insurance_2024.pdf`. By June a new copy lands as `insurance_new.pdf`.
Four files, four naming conventions, one current, three clutter, zero consistency.

### The gap in the market

Enterprise Content Management systems (SharePoint, OpenText, Documentum) solve this
for Fortune 500 companies at $50K-$500K per year. Consumer cloud storage (Dropbox,
iCloud, Google Drive) gives you a bucket but zero intelligence. The gap between those
two is enormous: small businesses, law offices, medical practices, insurance agencies,
real estate firms, solo professionals, families, veterans navigating claims -- they all
have the problem and have nothing between "folders I made in 2019" and a six-figure
enterprise system.

### The cost of the mess

| Stat | Source |
|------|--------|
| Average knowledge worker spends 9.3 hours/week searching for information | McKinsey Global Institute |
| 83% of workers recreate documents that already exist because they cannot find them | Wakefield Research |
| 21% of daily productivity is lost to document challenges | IDC |
| Duplicate files consume 20-40% of cloud storage costs | Veritas |
| 7.5% of all documents get lost entirely | IDC Research |
| US businesses spend $8 billion/year managing documents | Gartner |

For individuals the cost is less visible but just as real: the VA letter you cannot
find at 11pm before a filing deadline, the tax document on April 14th, the contract a
client asks for while you spend 40 minutes digging.

---

## The Insight

Two things changed that make this problem solvable now:

### 1. AI made organization free

Before AI, organizing files was pure labor. A human had to open every file, read it,
decide where it goes, move it, name it properly. Nobody does that voluntarily.

Now a classification engine reads a PDF in milliseconds, extracts content, matches it
against patterns, and routes it -- without a human touching it. The cost of organizing
went from hours of labor to zero. When organization is free and automatic, "just search
for it" stops being the smart move and starts being the lazy one.

### 2. Files have DNA

Every file has an identity that nobody captures:

| Field | Example |
|-------|---------|
| Origin | Downloaded from email attachment, sender: attorney@lawfirm.com |
| Created by | Adobe Acrobat, on Mike's MacBook |
| First seen | Jan 7, 2026, 3:22pm |
| Content fingerprint | SHA-256 hash + extracted text summary |
| Duplicates | 3 copies: iCloud, Downloads, Desktop |
| Canonical version | `/VA/08_Evidence_Documents/nexus_letter.pdf` |
| Related files | Same case: claim_increase.pdf, dbq_form.pdf |
| Last opened | Feb 19, 2026 |
| Tags (auto-extracted) | VA, disability, TDIU, neuropsych, 2026 |
| Lineage | Email -> Downloads -> In-Box -> VA (agent moved) |

That is not a file. That is a knowledge object. It knows what it is, where it came
from, what it is related to, and where it belongs.

---

## The Product

PRDTool is a document intelligence platform. It has three layers that build on
each other.

### Layer 1: The Roomba

An autonomous background agent that organizes files continuously.

- Runs hourly (or any interval) on your device or cloud
- Scans an In-Box folder for new files
- Classifies each file using rule-based keyword matching and PDF content extraction
- Routes files to the correct location based on a customizable taxonomy
- Never deletes anything -- only moves, with rollback capability
- Gets smarter from corrections: if you move a file back, the agent learns

The Roomba is what a user experiences. Drop a file anywhere. It ends up where it
belongs. You did nothing.

Like a real Roomba: you do not schedule time to clean. It just happens.

### Layer 2: The Brain

A knowledge graph that understands your documents.

- Every file gets a DNA record: content fingerprint, extracted metadata, auto-tags,
  origin tracking
- Lineage tracking: where did it come from, where has it been, who touched it
- Relationship mapping: files connected to the same case, project, client, or person
- Cross-platform dedup: detects duplicates across iCloud, Google Drive, Dropbox, local
- Storage health scoring: how much waste, how many duplicates, organization quality

The Brain enables a fundamentally different kind of search:

Without Brain:
> "Find my insurance policy"
> "I found 7 files with 'insurance' in the name. Here they are."

With Brain:
> "Find my insurance policy"
> "Your current auto policy is with USAA, effective March 2024. Here it is.
> There is also a rider amendment from August. Your previous State Farm policy
> is archived."

That is the difference between search and understanding.

### Layer 3: The Conduit

A consent-gated document pipeline for platforms.

Every financial application, insurance quote, medical intake, school enrollment, and
government form asks you to "upload these 8 documents." Document collection is the
number-one dropout point in every application flow. A mortgage application loses 40%
of applicants at document upload.

The Conduit connects the Brain to platforms that need documents:

- Rocket Mortgage requests your income documents
- You get a notification: "Rocket is requesting W-2, tax returns, bank statements.
  Your agent has all 8 documents ready."
- You tap Approve
- Documents are delivered in 4 seconds
- You did nothing except tap one button

The user never pays for the Conduit. The platform does -- because you saved them the
intake hassle. Just like Plaid: Venmo pays Plaid, not you.

But unlike Plaid, nothing is stored centrally. Documents flow directly from the user's
storage to the platform. Your servers facilitate the handshake but never hold the files.

---

## The Market

### Verticals

| Vertical | Pain Level | Why |
|----------|-----------|-----|
| Solo attorneys / small law firms | Extreme | Ethical obligation to organize case files; malpractice risk |
| Independent medical / therapy practices | High | HIPAA compliance, patient records management |
| Real estate agents / brokers | High | Contracts, disclosures, inspections per transaction |
| Insurance adjusters | High | Claims documentation across cases |
| Veterans / disability claimants | Very high | VA claims require meticulous evidence assembly |
| Freelancers / consultants | High | Client files, invoices, contracts, tax docs |
| Small businesses (5-50 employees) | High | No dedicated IT or document management staff |
| Families | Medium | School forms, medical records, finances, legal docs |

### Pricing: Intelligence-Based Tiers

Instead of charging for features or user seats, charge for how much the agent
understands about your life:

| Tier | Price | Contexts Unlocked |
|------|-------|-------------------|
| Starter (free) | $0 | 1 context (pick one: Work, Personal, or Finances). Agent is smart in that lane, blind everywhere else. |
| Focused | $3.99/mo | 3 contexts. Covers most professional needs. |
| Full Life | $7.99/mo | Unlimited contexts. Agent sees your whole world. |
| Family / Team | $12.99/mo | Unlimited + shared contexts for multiple people. |

Available contexts: Work, Finances, Legal, Health, Family, Education, Personal,
Photos/Media, VA/Government, Archive.

The upsell is organic: tax season arrives, agent says "I found 23 tax documents but
Finances is not in your plan." User upgrades. The mess itself is the pitch.

### Revenue Streams

| Stream | Who Pays | How |
|--------|----------|-----|
| Subscription | User | $3.99-12.99/mo for the agent |
| Conduit transaction fee | Platform | $1-5 per document package delivered |
| Lead generation | Platform | Pre-filled applications for mortgage, insurance, etc. |
| Vertical templates | Partners | White-label taxonomy templates for specific industries |

---

## The Moat

### 1. Accumulated intelligence

Every correction makes the system smarter. After 6 months, it knows your practice
better than your office manager. Switching means starting over with a dumb system and
re-teaching it for another year. Nobody does that.

### 2. Cross-platform visibility

The agent sees across Google Drive, Dropbox, iCloud, and local storage simultaneously.
No single platform will build this because it helps their competitors. You are the
Switzerland that works across all of them.

### 3. Privacy-first architecture

Files never leave the user's device (or their own cloud storage). The agent reads
metadata and content, but the centralized system only stores intelligence about files,
never the files themselves. If the server gets breached, the attacker gets metadata.
Not bank statements. Not medical records. Because you never had them.

### 4. Non-transferable knowledge graph

The relationship map -- which files relate to which case, which documents form a
complete claim, which versions are current -- is unique to each installation. It
cannot be exported to a competitor. It is the product.

---

## The Competitive Landscape

| Competitor | What They Do | What They Cannot Do |
|-----------|--------------|---------------------|
| Google Drive / Dropbox / iCloud | Store files | Organize, classify, deduplicate, or understand them |
| Plaid | Connect bank transaction data to apps | Handle documents, work across non-financial files |
| SharePoint / OpenText | Enterprise document management | Serve small businesses at $3.99/mo |
| Zapier / n8n | Move data between apps | Understand what is flowing through the pipes |
| HotDocs / Documate | Assemble new documents from templates | Manage documents after creation |
| Notion / Coda | Organize structured notes | Handle unstructured files (PDFs, scans, downloads) |

PRDTool occupies the gap between consumer storage (dumb buckets) and enterprise
ECM (overbuilt, overpriced). Nobody else sits here.

---

## The One-Liner

> Your documents already know the answer. We connect them to the question.

---

## Origin

This product was born from a real problem: an iCloud Drive with 350+ unorganized
root-level folders accumulated over a decade. The solution -- a Python classification
engine with a canonical taxonomy, a rule-based inbox processor, a learning correction
loop, and an autonomous background agent -- was built in a single engineering session.
The prototype works. The engine is running. Everything from here is packaging.
