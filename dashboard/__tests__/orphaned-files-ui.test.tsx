import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  OrphanedFileCard,
  OrphanedFilesList,
  OrphanedFilesFilter,
  OrphanedFilesBulkActionsBar,
  MissingFileCard,
  MissingFilesList,
  MissingFilesFilter,
  MissingFilesBulkActionsBar,
} from "@/components";
import type {
  OrphanedFileInfo,
  MissingFileInfo,
  EnhancedLocationSuggestion,
  OriginalLocationResult,
} from "@/lib/supabase";

// ============================================================================
// Mock Data
// ============================================================================

const mockOrphanedFile: OrphanedFileInfo = {
  filePath: "/Users/test/Documents/orphaned-file.pdf",
  fileName: "orphaned-file.pdf",
  fileSize: 1024 * 512, // 512 KB
  lastModified: "2024-01-15T10:00:00Z",
  fileType: "pdf",
  suggestedLocation: null,
  suggestedReason: null,
  confidence: 0,
};

const mockSuggestion: EnhancedLocationSuggestion = {
  suggestedPath: "/Users/test/Documents/Resumes",
  reason: "Filename suggests this is a resume document",
  confidence: 0.85,
  matchType: "filename_pattern",
  fromDatabase: false,
  databaseDocumentId: null,
  detectedCategory: "employment",
  similarFilesCount: 0,
};

const mockSuggestionFromDb: EnhancedLocationSuggestion = {
  suggestedPath: "/Users/test/Documents/Original",
  reason: "File found in database - restoring to original location",
  confidence: 0.95,
  matchType: "database_history",
  fromDatabase: true,
  databaseDocumentId: "doc-123",
  detectedCategory: null,
  similarFilesCount: 0,
};

const mockSuggestionSimilarFiles: EnhancedLocationSuggestion = {
  suggestedPath: "/Users/test/Documents/Taxes",
  reason: "Based on 5 similar files in database with same folder pattern",
  confidence: 0.85,
  matchType: "similar_files",
  fromDatabase: true,
  databaseDocumentId: null,
  detectedCategory: "finances",
  similarFilesCount: 5,
};

const mockMissingFile: MissingFileInfo = {
  documentId: "doc-1",
  fileName: "missing-file.pdf",
  currentPath: "/Users/test/Documents/missing-file.pdf",
  originalPath: "/Users/test/Documents/Original/missing-file.pdf",
  aiCategory: "employment",
  lastKnownLocation: "/Users/test/Documents/Last/missing-file.pdf",
  isAccessible: false,
};

const mockOriginalLocation: OriginalLocationResult = {
  documentId: "doc-1",
  originalPath: "/Users/test/Documents/Original/missing-file.pdf",
  locationHistory: [
    {
      path: "/Users/test/Documents/Original/missing-file.pdf",
      locationType: "primary",
      createdAt: "2024-01-01T10:00:00Z",
      isAccessible: true,
    },
    {
      path: "/Users/test/Documents/missing-file.pdf",
      locationType: "current",
      createdAt: "2024-01-15T10:00:00Z",
      isAccessible: false,
    },
  ],
};

// ============================================================================
// OrphanedFileCard Tests
// ============================================================================
describe("OrphanedFileCard", () => {
  const mockHandlers = {
    onSelect: vi.fn(),
    onAnalyze: vi.fn(),
    onMove: vi.fn(),
    onPathClick: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders file name and path", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("orphaned-file.pdf")).toBeInTheDocument();
  });

  it("shows file type badge", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("pdf")).toBeInTheDocument();
  });

  it("shows file size", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText(/Size:/)).toBeInTheDocument();
    expect(screen.getByText(/512.0 KB/)).toBeInTheDocument();
  });

  it("shows Analyze button when no suggestion", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("button", { name: "Analyze" })).toBeInTheDocument();
  });

  it("calls onAnalyze when Analyze button clicked", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    expect(mockHandlers.onAnalyze).toHaveBeenCalledWith(mockOrphanedFile.filePath);
  });

  it("shows suggestion details when suggestion is available", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={mockSuggestion}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("High confidence")).toBeInTheDocument();
    expect(screen.getByText("Filename pattern")).toBeInTheDocument();
    expect(screen.getByText(/Suggested:/)).toBeInTheDocument();
  });

  it("shows Move to Suggested button when suggestion available", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={mockSuggestion}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("button", { name: "Move to Suggested" })).toBeInTheDocument();
  });

  it("calls onMove when Move to Suggested clicked", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={mockSuggestion}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Move to Suggested" }));
    expect(mockHandlers.onMove).toHaveBeenCalledWith(
      mockOrphanedFile.filePath,
      mockSuggestion.suggestedPath
    );
  });

  it("shows From database badge when suggestion is from database", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={mockSuggestionFromDb}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("From database")).toBeInTheDocument();
    expect(screen.getByText("Found in database")).toBeInTheDocument();
  });

  it("shows Similar files badge when matched by similar files", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={mockSuggestionSimilarFiles}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Similar files")).toBeInTheDocument();
  });

  it("checkbox changes selection state", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    const checkbox = screen.getByRole("checkbox", { name: /Select orphaned-file.pdf/i });
    fireEvent.click(checkbox);
    expect(mockHandlers.onSelect).toHaveBeenCalledWith(mockOrphanedFile.filePath, true);
  });

  it("disables buttons when isLoading is true", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={null}
        isSelected={false}
        isLoading={true}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Analyzing...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyzing..." })).toBeDisabled();
  });

  it("calls onPathClick when path is clicked", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    const pathButton = screen.getByTitle(mockOrphanedFile.filePath);
    fireEvent.click(pathButton);
    expect(mockHandlers.onPathClick).toHaveBeenCalledWith(mockOrphanedFile.filePath);
  });

  it("shows details when expanded", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={mockSuggestionSimilarFiles}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    // Click to expand details
    fireEvent.click(screen.getByText(/Show details/));
    expect(screen.getByText(/Category:/)).toBeInTheDocument();
    expect(screen.getByText("finances")).toBeInTheDocument();
    expect(screen.getByText(/Similar files:/)).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("shows Re-analyze button always", () => {
    render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={mockSuggestion}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("button", { name: "Re-analyze" })).toBeInTheDocument();
  });

  it("applies selected styling when isSelected is true", () => {
    const { container } = render(
      <OrphanedFileCard
        file={mockOrphanedFile}
        suggestion={null}
        isSelected={true}
        isLoading={false}
        {...mockHandlers}
      />
    );

    const card = container.firstChild as HTMLElement;
    expect(card).toHaveClass("border-blue-500");
    expect(card).toHaveClass("bg-blue-50");
  });
});

// ============================================================================
// OrphanedFilesFilter Tests
// ============================================================================
describe("OrphanedFilesFilter", () => {
  const mockCounts = {
    all: 10,
    withSuggestion: 6,
    withoutSuggestion: 4,
    highConfidence: 3,
    lowConfidence: 3,
  };

  it("renders all filter buttons with counts", () => {
    const onFilterChange = vi.fn();
    render(
      <OrphanedFilesFilter
        filter="all"
        onFilterChange={onFilterChange}
        counts={mockCounts}
      />
    );

    expect(screen.getByText("All (10)")).toBeInTheDocument();
    expect(screen.getByText("With Suggestion (6)")).toBeInTheDocument();
    expect(screen.getByText("Needs Analysis (4)")).toBeInTheDocument();
    expect(screen.getByText("High Confidence (3)")).toBeInTheDocument();
    expect(screen.getByText("Low Confidence (3)")).toBeInTheDocument();
  });

  it("calls onFilterChange when filter button clicked", () => {
    const onFilterChange = vi.fn();
    render(
      <OrphanedFilesFilter
        filter="all"
        onFilterChange={onFilterChange}
        counts={mockCounts}
      />
    );

    fireEvent.click(screen.getByText("With Suggestion (6)"));
    expect(onFilterChange).toHaveBeenCalledWith("with_suggestion");
  });

  it("highlights active filter", () => {
    const onFilterChange = vi.fn();
    render(
      <OrphanedFilesFilter
        filter="with_suggestion"
        onFilterChange={onFilterChange}
        counts={mockCounts}
      />
    );

    const activeButton = screen.getByText("With Suggestion (6)");
    expect(activeButton).toHaveClass("bg-blue-600");
  });
});

// ============================================================================
// OrphanedFilesBulkActionsBar Tests
// ============================================================================
describe("OrphanedFilesBulkActionsBar", () => {
  const mockHandlers = {
    onAnalyzeAll: vi.fn(),
    onMoveAll: vi.fn(),
    onClearSelection: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not render when no items selected", () => {
    const { container } = render(
      <OrphanedFilesBulkActionsBar
        selectedCount={0}
        {...mockHandlers}
        isLoading={false}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders when items are selected", () => {
    render(
      <OrphanedFilesBulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={false}
      />
    );

    expect(screen.getByText((content, element) => {
      return element?.textContent === "3 files selected";
    })).toBeInTheDocument();
  });

  it("shows singular when 1 item selected", () => {
    render(
      <OrphanedFilesBulkActionsBar
        selectedCount={1}
        {...mockHandlers}
        isLoading={false}
      />
    );

    expect(screen.getByText((content, element) => {
      return element?.textContent === "1 file selected";
    })).toBeInTheDocument();
  });

  it("calls onAnalyzeAll when Analyze All clicked", () => {
    render(
      <OrphanedFilesBulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByText("Analyze All"));
    expect(mockHandlers.onAnalyzeAll).toHaveBeenCalled();
  });

  it("calls onMoveAll when Move All to Suggested clicked", () => {
    render(
      <OrphanedFilesBulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByText("Move All to Suggested"));
    expect(mockHandlers.onMoveAll).toHaveBeenCalled();
  });

  it("calls onClearSelection when Clear selection clicked", () => {
    render(
      <OrphanedFilesBulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByText("Clear selection"));
    expect(mockHandlers.onClearSelection).toHaveBeenCalled();
  });

  it("disables buttons when isLoading", () => {
    render(
      <OrphanedFilesBulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={true}
      />
    );

    expect(screen.getByText("Analyze All")).toBeDisabled();
    expect(screen.getByText("Move All to Suggested")).toBeDisabled();
  });
});

// ============================================================================
// OrphanedFilesList Tests
// ============================================================================
describe("OrphanedFilesList", () => {
  const mockFiles: OrphanedFileInfo[] = [
    mockOrphanedFile,
    {
      filePath: "/Users/test/Documents/another-orphan.txt",
      fileName: "another-orphan.txt",
      fileSize: 256,
      lastModified: "2024-01-10T10:00:00Z",
      fileType: "txt",
      suggestedLocation: null,
      suggestedReason: null,
      confidence: 0,
    },
  ];

  const mockHandlers = {
    onSelectFile: vi.fn(),
    onSelectAll: vi.fn(),
    onAnalyzeFile: vi.fn(),
    onMoveFile: vi.fn(),
    onPathClick: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty state when no files", () => {
    render(
      <OrphanedFilesList
        files={[]}
        suggestions={new Map()}
        selectedFiles={new Set()}
        loadingFiles={new Set()}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("No orphaned files found")).toBeInTheDocument();
  });

  it("renders file cards for each file", () => {
    render(
      <OrphanedFilesList
        files={mockFiles}
        suggestions={new Map()}
        selectedFiles={new Set()}
        loadingFiles={new Set()}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("orphaned-file.pdf")).toBeInTheDocument();
    expect(screen.getByText("another-orphan.txt")).toBeInTheDocument();
  });

  it("shows select all checkbox", () => {
    render(
      <OrphanedFilesList
        files={mockFiles}
        suggestions={new Map()}
        selectedFiles={new Set()}
        loadingFiles={new Set()}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("checkbox", { name: /Select all files/i })).toBeInTheDocument();
  });

  it("calls onSelectAll when select all is clicked", () => {
    render(
      <OrphanedFilesList
        files={mockFiles}
        suggestions={new Map()}
        selectedFiles={new Set()}
        loadingFiles={new Set()}
        {...mockHandlers}
      />
    );

    fireEvent.click(screen.getByRole("checkbox", { name: /Select all files/i }));
    expect(mockHandlers.onSelectAll).toHaveBeenCalledWith(true);
  });

  it("shows suggestion for file when available", () => {
    const suggestions = new Map<string, EnhancedLocationSuggestion>([
      [mockOrphanedFile.filePath, mockSuggestion],
    ]);

    render(
      <OrphanedFilesList
        files={mockFiles}
        suggestions={suggestions}
        selectedFiles={new Set()}
        loadingFiles={new Set()}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("High confidence")).toBeInTheDocument();
  });

  it("shows selected state for selected files", () => {
    const selectedFiles = new Set([mockOrphanedFile.filePath]);

    render(
      <OrphanedFilesList
        files={mockFiles}
        suggestions={new Map()}
        selectedFiles={selectedFiles}
        loadingFiles={new Set()}
        {...mockHandlers}
      />
    );

    const checkboxes = screen.getAllByRole("checkbox");
    const firstFileCheckbox = checkboxes[1]; // Skip "select all"
    expect(firstFileCheckbox).toBeChecked();
  });

  it("passes loading state to cards", () => {
    const loadingFiles = new Set([mockOrphanedFile.filePath]);

    render(
      <OrphanedFilesList
        files={mockFiles}
        suggestions={new Map()}
        selectedFiles={new Set()}
        loadingFiles={loadingFiles}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Analyzing...")).toBeInTheDocument();
  });
});

// ============================================================================
// MissingFileCard Tests
// ============================================================================
describe("MissingFileCard", () => {
  const mockHandlers = {
    onSelect: vi.fn(),
    onGetOriginal: vi.fn(),
    onRestore: vi.fn(),
    onUpdatePath: vi.fn(),
    onRemove: vi.fn(),
    onMarkInaccessible: vi.fn(),
    onPathClick: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders file name and current path", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("missing-file.pdf")).toBeInTheDocument();
    expect(screen.getByText(/Missing at:/)).toBeInTheDocument();
  });

  it("shows category badge when available", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("employment")).toBeInTheDocument();
  });

  it("shows Missing badge when file is not accessible", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Missing")).toBeInTheDocument();
  });

  it("shows original path when available", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText(/Original:/)).toBeInTheDocument();
  });

  it("shows Get Original button when no original location", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("button", { name: "Get Original" })).toBeInTheDocument();
  });

  it("calls onGetOriginal when Get Original clicked", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Get Original" }));
    expect(mockHandlers.onGetOriginal).toHaveBeenCalledWith(mockMissingFile.documentId);
  });

  it("shows Restore to Original button when original location available", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={mockOriginalLocation}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("button", { name: "Restore to Original" })).toBeInTheDocument();
  });

  it("calls onRestore when Restore to Original clicked", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={mockOriginalLocation}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Restore to Original" }));
    expect(mockHandlers.onRestore).toHaveBeenCalledWith(
      mockMissingFile.documentId,
      mockOriginalLocation.originalPath
    );
  });

  it("shows Update Path button", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("button", { name: "Update Path" })).toBeInTheDocument();
  });

  it("shows Mark Inaccessible button", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("button", { name: "Mark Inaccessible" })).toBeInTheDocument();
  });

  it("shows Remove from DB button", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("button", { name: "Remove from DB" })).toBeInTheDocument();
  });

  it("calls onRemove when Remove from DB clicked", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove from DB" }));
    expect(mockHandlers.onRemove).toHaveBeenCalledWith(mockMissingFile.documentId);
  });

  it("shows location history when expanded", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={mockOriginalLocation}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    // Click to expand location history
    fireEvent.click(screen.getByText(/Show location history/));
    expect(screen.getByText("Primary")).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();
  });

  it("checkbox changes selection state", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    const checkbox = screen.getByRole("checkbox", { name: /Select missing-file.pdf/i });
    fireEvent.click(checkbox);
    expect(mockHandlers.onSelect).toHaveBeenCalledWith(mockMissingFile.documentId, true);
  });

  it("disables buttons when isLoading is true", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={null}
        isSelected={false}
        isLoading={true}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Loading..." })).toBeDisabled();
  });

  it("shows update path form when Update Path clicked", () => {
    render(
      <MissingFileCard
        file={mockMissingFile}
        originalLocation={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Update Path" }));
    expect(screen.getByPlaceholderText("/path/to/file")).toBeInTheDocument();
  });
});

// ============================================================================
// MissingFilesFilter Tests
// ============================================================================
describe("MissingFilesFilter", () => {
  const mockCounts = {
    all: 10,
    withOriginal: 7,
    withoutOriginal: 3,
  };

  it("renders all filter buttons with counts", () => {
    const onFilterChange = vi.fn();
    render(
      <MissingFilesFilter
        filter="all"
        onFilterChange={onFilterChange}
        counts={mockCounts}
      />
    );

    expect(screen.getByText("All (10)")).toBeInTheDocument();
    expect(screen.getByText("Has Original (7)")).toBeInTheDocument();
    expect(screen.getByText("No Original (3)")).toBeInTheDocument();
  });

  it("calls onFilterChange when filter button clicked", () => {
    const onFilterChange = vi.fn();
    render(
      <MissingFilesFilter
        filter="all"
        onFilterChange={onFilterChange}
        counts={mockCounts}
      />
    );

    fireEvent.click(screen.getByText("Has Original (7)"));
    expect(onFilterChange).toHaveBeenCalledWith("with_original");
  });

  it("highlights active filter", () => {
    const onFilterChange = vi.fn();
    render(
      <MissingFilesFilter
        filter="with_original"
        onFilterChange={onFilterChange}
        counts={mockCounts}
      />
    );

    const activeButton = screen.getByText("Has Original (7)");
    expect(activeButton).toHaveClass("bg-blue-600");
  });

  it("shows category dropdown when categories provided", () => {
    const onFilterChange = vi.fn();
    const onCategoryChange = vi.fn();
    render(
      <MissingFilesFilter
        filter="all"
        onFilterChange={onFilterChange}
        counts={mockCounts}
        categories={["employment", "finances", "legal"]}
        onCategoryChange={onCategoryChange}
      />
    );

    expect(screen.getByText("Category:")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("calls onCategoryChange when category selected", () => {
    const onFilterChange = vi.fn();
    const onCategoryChange = vi.fn();
    render(
      <MissingFilesFilter
        filter="all"
        onFilterChange={onFilterChange}
        counts={mockCounts}
        categories={["employment", "finances", "legal"]}
        onCategoryChange={onCategoryChange}
      />
    );

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "employment" } });
    expect(onCategoryChange).toHaveBeenCalledWith("employment");
  });
});

// ============================================================================
// MissingFilesBulkActionsBar Tests
// ============================================================================
describe("MissingFilesBulkActionsBar", () => {
  const mockHandlers = {
    onGetOriginalAll: vi.fn(),
    onRestoreAll: vi.fn(),
    onRemoveAll: vi.fn(),
    onMarkInaccessibleAll: vi.fn(),
    onClearSelection: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not render when no items selected", () => {
    const { container } = render(
      <MissingFilesBulkActionsBar
        selectedCount={0}
        {...mockHandlers}
        isLoading={false}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders when items are selected", () => {
    render(
      <MissingFilesBulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={false}
      />
    );

    expect(screen.getByText((content, element) => {
      return element?.textContent === "3 files selected";
    })).toBeInTheDocument();
  });

  it("calls onGetOriginalAll when Get Originals clicked", () => {
    render(
      <MissingFilesBulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByText("Get Originals"));
    expect(mockHandlers.onGetOriginalAll).toHaveBeenCalled();
  });

  it("calls onRestoreAll when Restore All clicked", () => {
    render(
      <MissingFilesBulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByText("Restore All"));
    expect(mockHandlers.onRestoreAll).toHaveBeenCalled();
  });

  it("calls onMarkInaccessibleAll when Mark Inaccessible clicked", () => {
    render(
      <MissingFilesBulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByText("Mark Inaccessible"));
    expect(mockHandlers.onMarkInaccessibleAll).toHaveBeenCalled();
  });

  it("calls onRemoveAll when Remove All clicked", () => {
    render(
      <MissingFilesBulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByText("Remove All"));
    expect(mockHandlers.onRemoveAll).toHaveBeenCalled();
  });

  it("disables buttons when isLoading", () => {
    render(
      <MissingFilesBulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={true}
      />
    );

    expect(screen.getByText("Get Originals")).toBeDisabled();
    expect(screen.getByText("Restore All")).toBeDisabled();
    expect(screen.getByText("Remove All")).toBeDisabled();
    expect(screen.getByText("Mark Inaccessible")).toBeDisabled();
  });
});

// ============================================================================
// MissingFilesList Tests
// ============================================================================
describe("MissingFilesList", () => {
  const mockFiles: MissingFileInfo[] = [
    mockMissingFile,
    {
      documentId: "doc-2",
      fileName: "another-missing.pdf",
      currentPath: "/Users/test/Documents/another-missing.pdf",
      originalPath: null,
      aiCategory: "finances",
      lastKnownLocation: null,
      isAccessible: false,
    },
  ];

  const mockHandlers = {
    onSelectFile: vi.fn(),
    onSelectAll: vi.fn(),
    onGetOriginal: vi.fn(),
    onRestoreFile: vi.fn(),
    onUpdatePath: vi.fn(),
    onRemoveFile: vi.fn(),
    onMarkInaccessible: vi.fn(),
    onPathClick: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty state when no files", () => {
    render(
      <MissingFilesList
        files={[]}
        originalLocations={new Map()}
        selectedFiles={new Set()}
        loadingFiles={new Set()}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("No missing files found")).toBeInTheDocument();
  });

  it("renders file cards for each file", () => {
    render(
      <MissingFilesList
        files={mockFiles}
        originalLocations={new Map()}
        selectedFiles={new Set()}
        loadingFiles={new Set()}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("missing-file.pdf")).toBeInTheDocument();
    expect(screen.getByText("another-missing.pdf")).toBeInTheDocument();
  });

  it("shows select all checkbox", () => {
    render(
      <MissingFilesList
        files={mockFiles}
        originalLocations={new Map()}
        selectedFiles={new Set()}
        loadingFiles={new Set()}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("checkbox", { name: /Select all files/i })).toBeInTheDocument();
  });

  it("calls onSelectAll when select all is clicked", () => {
    render(
      <MissingFilesList
        files={mockFiles}
        originalLocations={new Map()}
        selectedFiles={new Set()}
        loadingFiles={new Set()}
        {...mockHandlers}
      />
    );

    fireEvent.click(screen.getByRole("checkbox", { name: /Select all files/i }));
    expect(mockHandlers.onSelectAll).toHaveBeenCalledWith(true);
  });

  it("shows original location for file when available", () => {
    const originalLocations = new Map<string, OriginalLocationResult>([
      [mockMissingFile.documentId, mockOriginalLocation],
    ]);

    render(
      <MissingFilesList
        files={mockFiles}
        originalLocations={originalLocations}
        selectedFiles={new Set()}
        loadingFiles={new Set()}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("button", { name: "Restore to Original" })).toBeInTheDocument();
  });

  it("shows selected state for selected files", () => {
    const selectedFiles = new Set([mockMissingFile.documentId]);

    render(
      <MissingFilesList
        files={mockFiles}
        originalLocations={new Map()}
        selectedFiles={selectedFiles}
        loadingFiles={new Set()}
        {...mockHandlers}
      />
    );

    const checkboxes = screen.getAllByRole("checkbox");
    const firstFileCheckbox = checkboxes[1]; // Skip "select all"
    expect(firstFileCheckbox).toBeChecked();
  });

  it("passes loading state to cards", () => {
    const loadingFiles = new Set([mockMissingFile.documentId]);

    render(
      <MissingFilesList
        files={mockFiles}
        originalLocations={new Map()}
        selectedFiles={new Set()}
        loadingFiles={loadingFiles}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});

// ============================================================================
// Component Exports Tests
// ============================================================================
describe("Component exports", () => {
  it("exports OrphanedFileCard", () => {
    expect(OrphanedFileCard).toBeDefined();
  });

  it("exports OrphanedFilesList", () => {
    expect(OrphanedFilesList).toBeDefined();
  });

  it("exports OrphanedFilesFilter", () => {
    expect(OrphanedFilesFilter).toBeDefined();
  });

  it("exports OrphanedFilesBulkActionsBar", () => {
    expect(OrphanedFilesBulkActionsBar).toBeDefined();
  });

  it("exports MissingFileCard", () => {
    expect(MissingFileCard).toBeDefined();
  });

  it("exports MissingFilesList", () => {
    expect(MissingFilesList).toBeDefined();
  });

  it("exports MissingFilesFilter", () => {
    expect(MissingFilesFilter).toBeDefined();
  });

  it("exports MissingFilesBulkActionsBar", () => {
    expect(MissingFilesBulkActionsBar).toBeDefined();
  });
});
