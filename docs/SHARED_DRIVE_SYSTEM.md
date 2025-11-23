# Shared Drive System

## Overview

The shared drive system provides AI-powered document management with version control. Employees automatically generate and update documents (Word, Spreadsheet, PowerPoint) that are organized by department, employee, and project. All documents are AI-generated using LLM, ensuring unique and contextual content.

## Features

- **AI-Powered Document Generation**: All documents created using LLM (no hardcoded content)
- **Multiple Document Types**: Word documents, Spreadsheets, PowerPoint presentations
- **Version Control**: Complete version history with change summaries
- **Organized Storage**: Documents organized by department/employee/project
- **Automatic Updates**: Documents automatically updated based on business context
- **Recent Files Tracking**: Track recently accessed files
- **Document Viewing**: HTML-based document viewing interface
- **Change Summaries**: AI-generated summaries of document changes

## How It Works

### Document Generation

**Automatic Generation**:
- Employees automatically generate documents during work
- Documents created based on:
  - Current projects
  - Tasks being worked on
  - Business context
  - Employee role and department

**Document Types**:
1. **Word Documents** (.docx format, stored as HTML):
   - Reports, proposals, documentation
   - Project updates, status reports
   - Meeting notes, summaries

2. **Spreadsheets** (.xlsx format, stored as HTML):
   - Budgets, financial analysis
   - Project timelines, task lists
   - Data analysis, metrics tracking

3. **PowerPoint Presentations** (.pptx format, stored as HTML):
   - Project presentations
   - Status updates, demos
   - Strategic planning decks

### Document Organization

Documents are organized in a hierarchical structure:
```
shared_drive/
  {department}/
    {employee_name}/
      {project_name}/
        {file_name}
```

**Organization Factors**:
- **Department**: Engineering, Sales, HR, etc.
- **Employee**: Creator/owner of document
- **Project**: Associated project (if applicable)
- **File Type**: Word, Spreadsheet, or PowerPoint

### Version Control

**Version Management**:
- Each document has a version number
- New versions created when document is updated
- Previous versions stored in `SharedDriveFileVersion` table
- Change summaries generated using AI

**Version History**:
- Complete history of all changes
- Who made changes
- When changes were made
- AI-generated change summaries

### Document Updates

**Automatic Updates**:
- Documents updated periodically (every 20-30 minutes)
- Updates based on:
  - Current business context
  - Project progress
  - Task completion
  - Financial changes

**Update Process**:
1. System selects documents to update
2. Retrieves current document content
3. Generates updated content using LLM
4. Creates new version with change summary
5. Updates document metadata

## Database Structure

### SharedDriveFile Table

```sql
CREATE TABLE shared_drive_files (
    id INTEGER PRIMARY KEY,
    file_name VARCHAR(255),
    file_type VARCHAR(50),  -- 'word', 'spreadsheet', 'powerpoint'
    file_path VARCHAR(500),
    content_html TEXT,
    file_size INTEGER,
    department VARCHAR(255),
    employee_id INTEGER REFERENCES employees(id),
    project_id INTEGER REFERENCES projects(id),
    current_version INTEGER DEFAULT 1,
    created_by_id INTEGER REFERENCES employees(id),
    last_updated_by_id INTEGER REFERENCES employees(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    file_metadata JSONB
);
```

### SharedDriveFileVersion Table

```sql
CREATE TABLE shared_drive_file_versions (
    id INTEGER PRIMARY KEY,
    file_id INTEGER REFERENCES shared_drive_files(id),
    version_number INTEGER,
    content_html TEXT,
    file_size INTEGER,
    created_by_id INTEGER REFERENCES employees(id),
    change_summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    file_metadata JSONB
);
```

## API Endpoints

### Get Shared Drive Files

```
GET /api/shared-drive/files?department=Engineering&employee_id=45&project_id=123&limit=50
```

**Response**:
```json
[
  {
    "id": 1,
    "file_name": "Project Status Report.docx",
    "file_type": "word",
    "file_path": "Engineering/John Doe/Project Alpha/Project Status Report.docx",
    "file_size": 15234,
    "department": "Engineering",
    "employee_id": 45,
    "employee_name": "John Doe",
    "project_id": 123,
    "project_name": "Project Alpha",
    "current_version": 3,
    "created_by_id": 45,
    "last_updated_by_id": 45,
    "created_at": "2024-01-10T10:00:00-05:00",
    "updated_at": "2024-01-15T14:30:00-05:00"
  }
]
```

### Get File Content

```
GET /api/shared-drive/files/{file_id}/view
```

**Response**: HTML content of the document

### Get File Versions

```
GET /api/shared-drive/files/{file_id}/versions
```

**Response**:
```json
[
  {
    "id": 1,
    "version_number": 3,
    "file_size": 15234,
    "created_by_id": 45,
    "created_by_name": "John Doe",
    "change_summary": "Updated project status with latest progress, added new milestones, and revised timeline.",
    "created_at": "2024-01-15T14:30:00-05:00",
    "metadata": {}
  },
  {
    "id": 2,
    "version_number": 2,
    "file_size": 14200,
    "created_by_id": 45,
    "created_by_name": "John Doe",
    "change_summary": "Added budget section and updated task list.",
    "created_at": "2024-01-12T10:00:00-05:00",
    "metadata": {}
  }
]
```

### Get File Version Content

```
GET /api/shared-drive/files/{file_id}/versions/{version_number}
```

**Response**:
```json
{
  "id": 1,
  "file_id": 1,
  "version_number": 2,
  "content_html": "<h1>Previous version content...</h1>",
  "file_size": 14200,
  "created_by_id": 45,
  "created_by_name": "John Doe",
  "change_summary": "Added budget section and updated task list.",
  "created_at": "2024-01-12T10:00:00-05:00",
  "metadata": {}
}
```

### Get Employee Recent Files

```
GET /api/employees/{employee_id}/recent-files?limit=15
```

**Response**:
```json
[
  {
    "id": 1,
    "file_name": "Project Status Report.docx",
    "file_type": "word",
    "updated_at": "2024-01-15T14:30:00-05:00",
    "project_name": "Project Alpha"
  }
]
```

## Frontend Integration

### Shared Drive View

**File**: `frontend/src/pages/SharedDrive.jsx` (if exists)

**Features**:
- File browser with filtering
- Document preview
- Version history viewer
- Recent files list
- Search functionality

### Document Viewer

**File**: `frontend/src/components/DocumentViewer.jsx` (if exists)

**Features**:
- HTML document rendering
- Version comparison
- Change summary display
- Download functionality

## Implementation

### SharedDriveManager Class

**File**: `backend/business/shared_drive_manager.py`

**Key Methods**:

```python
async def generate_word_document(
    self,
    employee: Employee,
    project: Optional[Project] = None,
    task: Optional[Task] = None,
    business_context: Optional[Dict] = None
) -> str:
    """Generate a Word document using AI."""
    
async def generate_spreadsheet(
    self,
    employee: Employee,
    project: Optional[Project] = None,
    task: Optional[Task] = None,
    business_context: Optional[Dict] = None
) -> str:
    """Generate a Spreadsheet using AI."""
    
async def generate_powerpoint(
    self,
    employee: Employee,
    project: Optional[Project] = None,
    task: Optional[Task] = None,
    business_context: Optional[Dict] = None
) -> str:
    """Generate a PowerPoint presentation using AI."""
    
async def create_new_version(
    self,
    file: SharedDriveFile,
    new_content: str,
    employee: Employee
) -> SharedDriveFileVersion:
    """Create a new version entry when a file is updated."""
    
async def generate_change_summary(
    self,
    old_content: str,
    new_content: str,
    employee: Employee
) -> str:
    """Generate change summary using AI."""
    
async def generate_documents_for_employee(
    self,
    employee: Employee,
    business_context: Optional[Dict] = None,
    max_documents: int = 1
) -> List[SharedDriveFile]:
    """Generate new documents for an employee."""
    
async def update_existing_documents(
    self,
    employee: Employee,
    business_context: Optional[Dict] = None,
    max_updates: int = 1
) -> List[SharedDriveFile]:
    """Update existing documents for an employee."""
```

### Integration with Office Simulator

The shared drive manager is called periodically:
- **Document Generation**: Every 20-30 minutes
- **Document Updates**: Every 20-30 minutes
- **Background Task**: Runs asynchronously

### Integration with Training System

Training materials are saved to shared drive:
- Materials accessible to all employees
- Organized by department
- Version controlled

## Configuration

### Document Generation Frequency

- **New Documents**: Up to 1 per employee per cycle
- **Document Updates**: Up to 1 per employee per cycle
- **Cycle Time**: Every 20-30 minutes

### File Storage

- **Base Directory**: `backend/shared_drive/`
- **Organization**: Department/Employee/Project structure
- **File Format**: HTML (for viewing in browser)

### Version Control

- **Version Numbering**: Incremental (1, 2, 3, ...)
- **Change Summaries**: AI-generated
- **Version Storage**: All versions stored in database

## Troubleshooting

### Documents Not Generating

**Possible Causes**:
1. LLM (Ollama) not available
2. AI generation failing
3. Database connection issues
4. File system permissions

**Solution**: Check Ollama connection, verify file permissions, check database

### Version History Not Working

**Possible Causes**:
1. Version creation failing
2. Change summary generation failing
3. Database transaction issues

**Solution**: Check version creation logic, verify change summary generation, check database

### Documents Not Updating

**Possible Causes**:
1. Update task not running
2. Business context missing
3. Document selection logic failing

**Solution**: Check background task, verify business context, check document selection

## Best Practices

1. **AI Generation**: Always use LLM for document generation
2. **Version Control**: Create versions for all updates
3. **Organization**: Maintain clear folder structure
4. **Change Summaries**: Generate meaningful change summaries
5. **Metadata**: Store useful metadata in file_metadata field
6. **Performance**: Limit document generation per cycle

## Future Enhancements

Potential improvements:
- Document collaboration (multiple editors)
- Document comments and annotations
- Document sharing and permissions
- Document templates
- Document search and indexing
- Document export (PDF, DOCX, etc.)
- Document tags and categories
- Document approval workflow
- Document analytics (views, edits)
- Real-time document editing

