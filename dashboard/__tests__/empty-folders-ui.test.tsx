import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  EmptyFolderCard,
  EmptyFoldersList,
  EmptyFoldersFilter,
  BulkActionsBar,
} from "@/components";
import type { EmptyFolderInfo, FolderAssessment, MovedFileInfo } from "@/lib/supabase";

// Mock data
const mockMovedFile: MovedFileInfo = {
  documentId: "doc-1",
  fileName: "test-file.pdf",
  originalPath: "/old/path/test-file.pdf",
  currentPath: "/new/path/test-file.pdf",
  movedAt: "2024-01-15T10:00:00Z",
};

const mockEmptyFolder: EmptyFolderInfo = {
  folderPath: "/Users/test/Documents/OldFolder",
  originalFileCount: 3,
  movedFiles: [mockMovedFile],
  isEmpty: true,
  lastMoveDate: "2024-01-15T10:00:00Z",
};

const mockAssessmentCorrect: FolderAssessment = {
  folderPath: "/Users/test/Documents/OldFolder",
  folderName: "OldFolder",
  isCorrectLocation: true,
  isDuplicate: false,
  assessment: "correct",
  confidence: 0.85,
  reasoning: ["Folder name matches AI category", "Files were correctly organized"],
  suggestedAction: "restore",
  movedFilesCategories: ["employment"],
  dominantCategory: "employment",
  categoryMatch: true,
  folderHierarchyMatch: true,
  canonicalMatch: false,
  similarCanonicalFolder: null,
  canonicalRegistryMatch: false,
  executionLogMatch: false,
  executionLogMovements: 0,
};

const mockAssessmentDuplicate: FolderAssessment = {
  folderPath: "/Users/test/Documents/Resumes2",
  folderName: "Resumes2",
  isCorrectLocation: false,
  isDuplicate: true,
  assessment: "duplicate",
  confidence: 0.7,
  reasoning: ["Folder appears to be a duplicate"],
  suggestedAction: "remove",
  movedFilesCategories: ["employment"],
  dominantCategory: "employment",
  categoryMatch: false,
  folderHierarchyMatch: false,
  canonicalMatch: false,
  similarCanonicalFolder: "Resumes",
  canonicalRegistryMatch: false,
  executionLogMatch: false,
  executionLogMovements: 0,
};

// ============================================================================
// EmptyFolderCard Tests
// ============================================================================
describe("EmptyFolderCard", () => {
  const mockHandlers = {
    onSelect: vi.fn(),
    onAssess: vi.fn(),
    onRestore: vi.fn(),
    onRemove: vi.fn(),
    onKeep: vi.fn(),
    onPathClick: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders folder name and path", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("OldFolder")).toBeInTheDocument();
    // Path should be clickable
    expect(screen.getByRole("button", { name: /OldFolder/i })).toBeInTheDocument();
  });

  it("shows Empty badge when folder is empty", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Empty")).toBeInTheDocument();
  });

  it("shows Not Empty badge when folder is not empty", () => {
    const notEmptyFolder = { ...mockEmptyFolder, isEmpty: false };
    render(
      <EmptyFolderCard
        folder={notEmptyFolder}
        assessment={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Not Empty")).toBeInTheDocument();
  });

  it("shows Not assessed badge when no assessment", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Not assessed")).toBeInTheDocument();
  });

  it("shows Correct Location badge when assessment is correct", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={mockAssessmentCorrect}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Correct Location")).toBeInTheDocument();
  });

  it("shows Duplicate/Misnamed badge when assessment is duplicate", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={mockAssessmentDuplicate}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Duplicate/Misnamed")).toBeInTheDocument();
  });

  it("shows file count and last move date", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    // Text is split across span and text node, use getAllByText and check first match
    const fileCountElements = screen.getAllByText((content, element) => {
      // Only match the specific span element containing this text
      return element?.tagName === "SPAN" && element?.textContent === "3 files moved";
    });
    expect(fileCountElements.length).toBeGreaterThan(0);
    expect(screen.getByText(/Last moved:/)).toBeInTheDocument();
  });

  it("shows Assess button when no assessment", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("button", { name: "Assess" })).toBeInTheDocument();
  });

  it("calls onAssess when Assess button clicked", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Assess" }));
    expect(mockHandlers.onAssess).toHaveBeenCalledWith(mockEmptyFolder.folderPath);
  });

  it("shows Restore Files button when suggested action is restore", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={mockAssessmentCorrect}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("button", { name: "Restore Files" })).toBeInTheDocument();
  });

  it("shows Remove Folder button when suggested action is remove", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={mockAssessmentDuplicate}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("button", { name: "Remove Folder" })).toBeInTheDocument();
  });

  it("always shows Keep Folder button", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("button", { name: "Keep Folder" })).toBeInTheDocument();
  });

  it("calls onRestore when Restore Files clicked", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={mockAssessmentCorrect}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Restore Files" }));
    expect(mockHandlers.onRestore).toHaveBeenCalledWith(mockEmptyFolder.folderPath);
  });

  it("calls onRemove when Remove Folder clicked", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={mockAssessmentDuplicate}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove Folder" }));
    expect(mockHandlers.onRemove).toHaveBeenCalledWith(mockEmptyFolder.folderPath);
  });

  it("calls onKeep when Keep Folder clicked", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Keep Folder" }));
    expect(mockHandlers.onKeep).toHaveBeenCalledWith(mockEmptyFolder.folderPath);
  });

  it("disables buttons when isLoading is true", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={null}
        isSelected={false}
        isLoading={true}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Assessing...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Assessing..." })).toBeDisabled();
  });

  it("checkbox changes selection state", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    const checkbox = screen.getByRole("checkbox", { name: /Select OldFolder/i });
    fireEvent.click(checkbox);
    expect(mockHandlers.onSelect).toHaveBeenCalledWith(mockEmptyFolder.folderPath, true);
  });

  it("shows reasoning when assessment has reasoning", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={mockAssessmentCorrect}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    // Click to expand reasoning
    fireEvent.click(screen.getByText(/Show reasoning/));
    expect(screen.getByText("Folder name matches AI category")).toBeInTheDocument();
  });

  it("shows dominant category when available", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={mockAssessmentCorrect}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    expect(screen.getByText(/Category:/)).toBeInTheDocument();
    expect(screen.getByText("employment")).toBeInTheDocument();
  });

  it("calls onPathClick when path is clicked", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    const pathButton = screen.getByTitle(mockEmptyFolder.folderPath);
    fireEvent.click(pathButton);
    expect(mockHandlers.onPathClick).toHaveBeenCalledWith(mockEmptyFolder.folderPath);
  });

  it("shows moved files when expanded", () => {
    render(
      <EmptyFolderCard
        folder={mockEmptyFolder}
        assessment={null}
        isSelected={false}
        isLoading={false}
        {...mockHandlers}
      />
    );

    // Click to expand moved files
    fireEvent.click(screen.getByText(/Show moved files/));
    expect(screen.getByText("test-file.pdf")).toBeInTheDocument();
  });
});

// ============================================================================
// EmptyFoldersFilter Tests
// ============================================================================
describe("EmptyFoldersFilter", () => {
  const mockCounts = {
    all: 10,
    empty: 6,
    notEmpty: 4,
    assessed: 3,
    unassessed: 7,
  };

  it("renders all filter buttons with counts", () => {
    const onFilterChange = vi.fn();
    render(
      <EmptyFoldersFilter
        filter="all"
        onFilterChange={onFilterChange}
        counts={mockCounts}
      />
    );

    expect(screen.getByText("All (10)")).toBeInTheDocument();
    expect(screen.getByText("Empty (6)")).toBeInTheDocument();
    expect(screen.getByText("Not Empty (4)")).toBeInTheDocument();
    expect(screen.getByText("Assessed (3)")).toBeInTheDocument();
    expect(screen.getByText("Unassessed (7)")).toBeInTheDocument();
  });

  it("calls onFilterChange when filter button clicked", () => {
    const onFilterChange = vi.fn();
    render(
      <EmptyFoldersFilter
        filter="all"
        onFilterChange={onFilterChange}
        counts={mockCounts}
      />
    );

    fireEvent.click(screen.getByText("Empty (6)"));
    expect(onFilterChange).toHaveBeenCalledWith("empty");
  });

  it("highlights active filter", () => {
    const onFilterChange = vi.fn();
    render(
      <EmptyFoldersFilter
        filter="empty"
        onFilterChange={onFilterChange}
        counts={mockCounts}
      />
    );

    const emptyButton = screen.getByText("Empty (6)");
    expect(emptyButton).toHaveClass("bg-blue-600");
  });
});

// ============================================================================
// BulkActionsBar Tests
// ============================================================================
describe("BulkActionsBar", () => {
  const mockHandlers = {
    onRemoveAll: vi.fn(),
    onRestoreAll: vi.fn(),
    onAssessAll: vi.fn(),
    onClearSelection: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not render when no items selected", () => {
    const { container } = render(
      <BulkActionsBar
        selectedCount={0}
        {...mockHandlers}
        isLoading={false}
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders when items are selected", () => {
    render(
      <BulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={false}
      />
    );

    // Text is split across span and text node, use a function matcher
    expect(screen.getByText((content, element) => {
      return element?.textContent === "3 folders selected";
    })).toBeInTheDocument();
  });

  it("shows singular when 1 item selected", () => {
    render(
      <BulkActionsBar
        selectedCount={1}
        {...mockHandlers}
        isLoading={false}
      />
    );

    // Text is split across span and text node, use a function matcher
    expect(screen.getByText((content, element) => {
      return element?.textContent === "1 folder selected";
    })).toBeInTheDocument();
  });

  it("calls onAssessAll when Assess All clicked", () => {
    render(
      <BulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByText("Assess All"));
    expect(mockHandlers.onAssessAll).toHaveBeenCalled();
  });

  it("calls onRestoreAll when Restore All clicked", () => {
    render(
      <BulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByText("Restore All"));
    expect(mockHandlers.onRestoreAll).toHaveBeenCalled();
  });

  it("calls onRemoveAll when Remove All clicked", () => {
    render(
      <BulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByText("Remove All"));
    expect(mockHandlers.onRemoveAll).toHaveBeenCalled();
  });

  it("calls onClearSelection when Clear selection clicked", () => {
    render(
      <BulkActionsBar
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
      <BulkActionsBar
        selectedCount={3}
        {...mockHandlers}
        isLoading={true}
      />
    );

    expect(screen.getByText("Assess All")).toBeDisabled();
    expect(screen.getByText("Restore All")).toBeDisabled();
    expect(screen.getByText("Remove All")).toBeDisabled();
  });
});

// ============================================================================
// EmptyFoldersList Tests
// ============================================================================
describe("EmptyFoldersList", () => {
  const mockFolders: EmptyFolderInfo[] = [
    mockEmptyFolder,
    {
      folderPath: "/Users/test/Documents/AnotherFolder",
      originalFileCount: 5,
      movedFiles: [],
      isEmpty: true,
      lastMoveDate: "2024-01-10T10:00:00Z",
    },
  ];

  const mockHandlers = {
    onSelectFolder: vi.fn(),
    onSelectAll: vi.fn(),
    onAssessFolder: vi.fn(),
    onRestoreFolder: vi.fn(),
    onRemoveFolder: vi.fn(),
    onKeepFolder: vi.fn(),
    onPathClick: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty state when no folders", () => {
    render(
      <EmptyFoldersList
        folders={[]}
        assessments={new Map()}
        selectedFolders={new Set()}
        loadingFolders={new Set()}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("No empty folders found")).toBeInTheDocument();
  });

  it("renders folder cards for each folder", () => {
    render(
      <EmptyFoldersList
        folders={mockFolders}
        assessments={new Map()}
        selectedFolders={new Set()}
        loadingFolders={new Set()}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("OldFolder")).toBeInTheDocument();
    expect(screen.getByText("AnotherFolder")).toBeInTheDocument();
  });

  it("shows select all checkbox", () => {
    render(
      <EmptyFoldersList
        folders={mockFolders}
        assessments={new Map()}
        selectedFolders={new Set()}
        loadingFolders={new Set()}
        {...mockHandlers}
      />
    );

    expect(screen.getByRole("checkbox", { name: /Select all folders/i })).toBeInTheDocument();
  });

  it("calls onSelectAll when select all is clicked", () => {
    render(
      <EmptyFoldersList
        folders={mockFolders}
        assessments={new Map()}
        selectedFolders={new Set()}
        loadingFolders={new Set()}
        {...mockHandlers}
      />
    );

    fireEvent.click(screen.getByRole("checkbox", { name: /Select all folders/i }));
    expect(mockHandlers.onSelectAll).toHaveBeenCalledWith(true);
  });

  it("shows assessment for folder when available", () => {
    const assessments = new Map<string, FolderAssessment>([
      [mockEmptyFolder.folderPath, mockAssessmentCorrect],
    ]);

    render(
      <EmptyFoldersList
        folders={mockFolders}
        assessments={assessments}
        selectedFolders={new Set()}
        loadingFolders={new Set()}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Correct Location")).toBeInTheDocument();
  });

  it("shows selected state for selected folders", () => {
    const selectedFolders = new Set([mockEmptyFolder.folderPath]);

    render(
      <EmptyFoldersList
        folders={mockFolders}
        assessments={new Map()}
        selectedFolders={selectedFolders}
        loadingFolders={new Set()}
        {...mockHandlers}
      />
    );

    // Find the card for the selected folder - it should have blue styling
    const checkboxes = screen.getAllByRole("checkbox");
    const firstFolderCheckbox = checkboxes[1]; // Skip "select all"
    expect(firstFolderCheckbox).toBeChecked();
  });

  it("passes loading state to cards", () => {
    const loadingFolders = new Set([mockEmptyFolder.folderPath]);

    render(
      <EmptyFoldersList
        folders={mockFolders}
        assessments={new Map()}
        selectedFolders={new Set()}
        loadingFolders={loadingFolders}
        {...mockHandlers}
      />
    );

    expect(screen.getByText("Assessing...")).toBeInTheDocument();
  });
});

// ============================================================================
// Component Exports Tests
// ============================================================================
describe("Component exports", () => {
  it("exports EmptyFolderCard", () => {
    expect(EmptyFolderCard).toBeDefined();
  });

  it("exports EmptyFoldersList", () => {
    expect(EmptyFoldersList).toBeDefined();
  });

  it("exports EmptyFoldersFilter", () => {
    expect(EmptyFoldersFilter).toBeDefined();
  });

  it("exports BulkActionsBar", () => {
    expect(BulkActionsBar).toBeDefined();
  });
});
