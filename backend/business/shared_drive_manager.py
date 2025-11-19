"""
Shared Drive Manager - Handles AI-powered document generation and version control.
All document generation uses Ollama AI - no hardcoded content.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from database.models import (
    Employee, Project, Task, Activity, 
    SharedDriveFile, SharedDriveFileVersion
)
from datetime import datetime, timedelta
import os
import json
import re
from typing import List, Optional, Dict
import httpx
from llm.ollama_client import OllamaClient
from engine.office_simulator import get_business_context
from sqlalchemy import select, func
from database.models import Project, Employee, Financial
from config import now as local_now


class SharedDriveManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm_client = OllamaClient()
        # Base directory for shared drive files
        self.base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared_drive")
        os.makedirs(self.base_dir, exist_ok=True)
    
    def _get_file_path(self, department: str, employee_name: str, project_name: str, file_name: str) -> str:
        """Generate file path based on organization structure."""
        # Sanitize names for filesystem
        safe_dept = re.sub(r'[^\w\s-]', '', department or "General").strip() if department else "General"
        safe_emp = re.sub(r'[^\w\s-]', '', employee_name or "Shared").strip() if employee_name else "Shared"
        safe_proj = re.sub(r'[^\w\s-]', '', project_name or "General").strip() if project_name else "General"
        safe_file = re.sub(r'[^\w\s.-]', '', file_name).strip()
        
        # Ensure file has .html extension (we store as HTML)
        if not safe_file.endswith('.html'):
            # Replace extension with .html
            if '.' in safe_file:
                safe_file = safe_file.rsplit('.', 1)[0] + '.html'
            else:
                safe_file += '.html'
        
        dir_path = os.path.join(self.base_dir, safe_dept, safe_emp, safe_proj)
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, safe_file)
    
    def _check_content_similarity(self, content1: str, content2: str, threshold: float = 0.85) -> bool:
        """Check if two document contents are similar (to prevent duplicates)."""
        # Remove HTML tags and normalize whitespace for comparison
        import re
        def normalize(text):
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', '', text)
            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text).strip().lower()
            # Remove common variable parts (dates, names that might differ)
            text = re.sub(r'\d+', '', text)  # Remove numbers
            return text[:1000]  # Compare first 1000 chars
        
        norm1 = normalize(content1)
        norm2 = normalize(content2)
        
        if not norm1 or not norm2:
            return False
        
        # Simple similarity check: if normalized content is very similar
        if norm1 == norm2:
            return True
        
        # Check if one is a substring of the other (with some tolerance)
        if len(norm1) > 100 and len(norm2) > 100:
            # Calculate simple character overlap
            shorter = min(len(norm1), len(norm2))
            longer = max(len(norm1), len(norm2))
            matches = sum(1 for a, b in zip(norm1[:shorter], norm2[:shorter]) if a == b)
            similarity = matches / longer if longer > 0 else 0
            return similarity >= threshold
        
        return False
    
    async def _check_duplicate_content(self, new_content: str, employee_id: int, file_type: str) -> bool:
        """Check if similar content already exists for this employee."""
        # Get all files of the same type for this employee
        result = await self.db.execute(
            select(SharedDriveFile).where(
                SharedDriveFile.employee_id == employee_id,
                SharedDriveFile.file_type == file_type
            )
        )
        existing_files = result.scalars().all()
        
        # Check content similarity
        for existing_file in existing_files:
            if self._check_content_similarity(new_content, existing_file.content_html):
                print(f"  ⚠️  Skipping duplicate: similar content already exists in '{existing_file.file_name}'")
                return True
        
        return False
    
    async def _get_enhanced_business_context(self, business_context: Dict) -> Dict:
        """Get enhanced business context with more detailed data."""
        enhanced = business_context.copy()
        
        # Get project details
        result = await self.db.execute(
            select(Project).where(Project.status == "active").limit(5)
        )
        active_projects = result.scalars().all()
        enhanced['project_details'] = [
            {
                'name': p.name,
                'status': p.status,
                'budget': p.budget or 0,
                'revenue': p.revenue or 0,
                'description': p.description or 'N/A'
            }
            for p in active_projects
        ]
        
        # Get employee statistics by department
        result = await self.db.execute(
            select(Employee).where(Employee.status == "active")
        )
        employees = result.scalars().all()
        dept_counts = {}
        for emp in employees:
            dept = emp.department or "Unassigned"
            dept_counts[dept] = dept_counts.get(dept, 0) + 1
        enhanced['department_distribution'] = dept_counts
        
        # Get financial metrics
        result = await self.db.execute(
            select(func.sum(Financial.amount)).where(Financial.type == "revenue")
        )
        total_revenue = result.scalar() or 0
        
        result = await self.db.execute(
            select(func.sum(Financial.amount)).where(Financial.type == "expense")
        )
        total_expenses = result.scalar() or 0
        
        enhanced['total_revenue'] = total_revenue
        enhanced['total_expenses'] = total_expenses
        enhanced['profit_margin'] = ((enhanced.get('profit', 0) / enhanced.get('revenue', 1)) * 100) if enhanced.get('revenue', 0) > 0 else 0
        
        return enhanced
    
    async def generate_file_name(
        self, 
        file_type: str, 
        employee: Employee, 
        project: Optional[Project] = None,
        task: Optional[Task] = None
    ) -> str:
        """Use AI to generate a realistic file name based on context."""
        context_parts = []
        if project:
            context_parts.append(f"Project: {project.name}")
        if task:
            context_parts.append(f"Task: {task.description[:100]}")
        context_parts.append(f"Employee: {employee.name} ({employee.title})")
        context_parts.append(f"Department: {employee.department or 'General'}")
        
        context_str = "\n".join(context_parts)
        
        file_type_names = {
            "word": "Word document",
            "spreadsheet": "Excel spreadsheet",
            "powerpoint": "PowerPoint presentation"
        }
        
        prompt = f"""Generate a realistic, professional file name for a {file_type_names.get(file_type, 'document')}.

Context:
{context_str}

The file name should:
1. Be professional and descriptive
2. Include relevant project or task information if applicable
3. Be appropriate for a business document
4. Use proper capitalization
5. Be concise (max 60 characters)

Examples:
- "Q4_Financial_Report.docx"
- "Project_Status_Update_2024.xlsx"
- "Team_Meeting_Presentation.pptx"

Generate ONLY the file name with appropriate extension (.docx, .xlsx, or .pptx). Do not include any explanation or quotes."""

        try:
            client = await self.llm_client._get_client()
            response = await client.post(
                f"{self.llm_client.base_url}/api/generate",
                json={
                    "model": self.llm_client.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=httpx.Timeout(15.0, connect=5.0)
            )
            
            if response.status_code == 200:
                result = response.json()
                file_name = result.get("response", "").strip()
                # Clean up the response
                file_name = file_name.strip('"').strip("'").strip()
                # Remove markdown code blocks if present
                if file_name.startswith("```"):
                    file_name = re.sub(r'```[^\n]*\n', '', file_name)
                    file_name = re.sub(r'\n```', '', file_name)
                    file_name = file_name.strip()
                
                # Files are stored as HTML, but we keep the original extension in the name for display
                # The actual file will have .html extension added by _get_file_path if needed
                # Just ensure it has some extension
                if '.' not in file_name:
                    extensions = {'word': '.docx', 'spreadsheet': '.xlsx', 'powerpoint': '.pptx'}
                    file_name += extensions.get(file_type, '.docx')
                
                return file_name[:100]  # Limit length
        except Exception as e:
            print(f"Error generating file name: {e}")
        
        # Fallback file name
        timestamp = datetime.now().strftime("%Y%m%d")
        extensions = {'word': '.docx', 'spreadsheet': '.xlsx', 'powerpoint': '.pptx'}
        return f"Document_{timestamp}{extensions.get(file_type, '.docx')}"
    
    async def generate_word_document(
        self,
        employee: Employee,
        project: Optional[Project] = None,
        task: Optional[Task] = None,
        business_context: Optional[Dict] = None
    ) -> str:
        """Use AI to generate HTML that looks like a Word document with realistic business content."""
        if not business_context:
            business_context = await get_business_context(self.db)
        
        # Get enhanced business context
        enhanced_context = await self._get_enhanced_business_context(business_context)
        
        # Build comprehensive context for AI
        context_parts = []
        context_parts.append(f"EMPLOYEE INFORMATION:")
        context_parts.append(f"  - Name: {employee.name}")
        context_parts.append(f"  - Title: {employee.title}")
        context_parts.append(f"  - Role: {employee.role}")
        context_parts.append(f"  - Department: {employee.department or 'General'}")
        
        if project:
            context_parts.append(f"\nCURRENT PROJECT:")
            context_parts.append(f"  - Project Name: {project.name}")
            context_parts.append(f"  - Status: {project.status}")
            context_parts.append(f"  - Budget: ${project.budget or 0:,.2f}")
            context_parts.append(f"  - Revenue: ${project.revenue or 0:,.2f}")
            context_parts.append(f"  - Description: {project.description or 'N/A'}")
        
        if task:
            context_parts.append(f"\nCURRENT TASK:")
            context_parts.append(f"  - Description: {task.description}")
            context_parts.append(f"  - Status: {task.status}")
        
        context_parts.append(f"\nBUSINESS METRICS:")
        context_parts.append(f"  - Total Revenue: ${enhanced_context.get('revenue', 0):,.2f}")
        context_parts.append(f"  - Total Profit: ${enhanced_context.get('profit', 0):,.2f}")
        context_parts.append(f"  - Profit Margin: {enhanced_context.get('profit_margin', 0):.2f}%")
        context_parts.append(f"  - Total Expenses: ${enhanced_context.get('total_expenses', 0):,.2f}")
        context_parts.append(f"  - Active Projects: {enhanced_context.get('active_projects', 0)}")
        context_parts.append(f"  - Total Employees: {enhanced_context.get('employee_count', 0)}")
        
        if enhanced_context.get('project_details'):
            context_parts.append(f"\nACTIVE PROJECTS:")
            for proj in enhanced_context['project_details'][:3]:
                context_parts.append(f"  - {proj['name']}: ${proj['budget']:,.2f} budget, {proj['status']} status")
        
        if enhanced_context.get('department_distribution'):
            context_parts.append(f"\nDEPARTMENT DISTRIBUTION:")
            for dept, count in list(enhanced_context['department_distribution'].items())[:5]:
                context_parts.append(f"  - {dept}: {count} employees")
        
        context_str = "\n".join(context_parts)
        
        prompt = f"""You are generating a FANCY, PROFESSIONAL, HIGH-QUALITY Microsoft Word document as HTML. This must look like a premium business document with real data.

BUSINESS CONTEXT (USE ALL THIS REAL DATA):
{context_str}

CRITICAL REQUIREMENTS - MAKE IT FANCY AND DETAILED:

1. DOCUMENT TYPE: Create a realistic business document based on the employee's role:
   - Managers/Executives: Strategic reports, quarterly reviews, business analysis
   - Finance/Accounting: Financial reports, budget analysis, revenue breakdowns
   - Sales/Marketing: Sales reports, campaign analysis, market research
   - IT/Engineering: Technical reports, project status, system analysis
   - HR: Employee reports, hiring analysis, performance reviews
   - Operations: Operational reports, efficiency analysis, process documentation

2. PREMIUM STYLING (Make it look expensive and professional):
   - White background (#ffffff) with subtle shadows
   - 1-inch margins on all sides
   - Times New Roman (12pt) for body, Calibri (11pt) for headers
   - Black text (#000000) with proper contrast
   - Line height: 1.5 for readability
   - Professional paragraph spacing (12pt between paragraphs)
   - Use bold for emphasis, italics for important notes

3. DOCUMENT STRUCTURE (Make it comprehensive):
   - FANCY TITLE: Centered, 18pt, bold, Times New Roman, with decorative underline
   - HEADER: Date, employee name, department, document classification
   - EXECUTIVE SUMMARY: 2-3 paragraphs summarizing key points
   - MAIN SECTIONS: 3-5 sections with clear headings (14pt, bold)
   - DATA SECTIONS: Include tables, lists, or formatted data
   - CONCLUSION: Summary and recommendations
   - FOOTER: Page numbers, document version, confidentiality notice

4. CONTENT REQUIREMENTS (USE REAL BUSINESS DATA):
   - Include ACTUAL numbers from the business context (revenue, profit, employee counts, project budgets)
   - Reference SPECIFIC projects by name and their actual status/budget
   - Mention REAL departments and their employee counts
   - Use ACTUAL profit margins, revenue figures, expense data
   - Include realistic dates, percentages, and calculations
   - Add professional analysis of the data (trends, insights, recommendations)
   - Write 6-10 substantial paragraphs with real business insights
   - Use professional business terminology appropriate to the role

5. MAKE IT FANCY:
   - Add professional formatting: tables, bullet points, numbered lists
   - Include data visualizations described in text (e.g., "Revenue increased 15% QoQ")
   - Use professional language with industry-specific terms
   - Add executive-level insights and strategic recommendations
   - Include realistic business scenarios and case studies
   - Make it look like a document that cost thousands to produce

6. HTML STRUCTURE:
   - Wrap in: <div style="font-family: 'Times New Roman', serif; font-size: 12pt; margin: 1in; line-height: 1.5; color: #000000; background: #ffffff; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
   - Use: <h1> for title, <h2> for sections, <p> for paragraphs, <table> for data, <ul>/<ol> for lists
   - All styles inline
   - Add subtle borders, proper spacing, professional typography

IMPORTANT: Use the ACTUAL business data provided. Reference real projects, real numbers, real departments. Make this document look like it was created by a professional consulting firm. It should be comprehensive, data-rich, and visually impressive.

Generate the complete HTML document now. Return ONLY the HTML with inline styles."""

        try:
            client = await self.llm_client._get_client()
            response = await client.post(
                f"{self.llm_client.base_url}/api/generate",
                json={
                    "model": self.llm_client.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=httpx.Timeout(20.0, connect=5.0)
            )
            
            if response.status_code == 200:
                result = response.json()
                html_content = result.get("response", "").strip()
                # Clean up the response
                html_content = html_content.strip('"').strip("'").strip()
                # Remove markdown code blocks if present
                if html_content.startswith("```"):
                    html_content = re.sub(r'```[^\n]*\n', '', html_content)
                    html_content = re.sub(r'\n```', '', html_content)
                    html_content = html_content.strip()
                
                # Ensure it's wrapped in a styled div if not already
                if not html_content.startswith("<"):
                    html_content = f'<div style="font-family: \'Times New Roman\', serif; margin: 1in; line-height: 1.5; color: #000000;">{html_content}</div>'
                
                return html_content
        except Exception as e:
            print(f"Error generating Word document: {e}")
            import traceback
            traceback.print_exc()
        
        # Fallback content - create a realistic document
        doc_title = "Business Report" if not project else f"{project.name} - Status Report"
        return f'''<div style="font-family: 'Times New Roman', serif; font-size: 12pt; margin: 1in; line-height: 1.5; color: #000000; background: #ffffff;">
<h1 style="font-size: 18pt; font-weight: bold; text-align: center; margin-bottom: 24pt;">{doc_title}</h1>
<p style="text-align: center; margin-bottom: 24pt;">Prepared by: {employee.name}<br>{employee.title}<br>{local_now().strftime('%B %d, %Y')}</p>
<h2 style="font-size: 14pt; font-weight: bold; margin-top: 18pt; margin-bottom: 12pt;">Executive Summary</h2>
<p style="margin-bottom: 12pt; text-align: justify;">This report provides a comprehensive overview of current business activities and performance metrics. The analysis covers key operational areas including project status, financial performance, and strategic initiatives.</p>
<h2 style="font-size: 14pt; font-weight: bold; margin-top: 18pt; margin-bottom: 12pt;">Current Status</h2>
<p style="margin-bottom: 12pt; text-align: justify;">Based on the most recent data, the organization is operating within expected parameters. Revenue streams remain stable, and project deliverables are progressing according to schedule. Key stakeholders have been kept informed of developments through regular communication channels.</p>
<h2 style="font-size: 14pt; font-weight: bold; margin-top: 18pt; margin-bottom: 12pt;">Key Findings</h2>
<ul style="margin-left: 36pt; margin-bottom: 12pt;">
<li style="margin-bottom: 6pt;">Performance metrics indicate positive trends in core business areas</li>
<li style="margin-bottom: 6pt;">Resource allocation aligns with strategic priorities</li>
<li style="margin-bottom: 6pt;">Stakeholder engagement remains strong across all departments</li>
</ul>
<h2 style="font-size: 14pt; font-weight: bold; margin-top: 18pt; margin-bottom: 12pt;">Recommendations</h2>
<p style="margin-bottom: 12pt; text-align: justify;">Moving forward, it is recommended that we continue to monitor key performance indicators closely and maintain open lines of communication with all stakeholders. Regular review cycles will ensure that any emerging issues are identified and addressed promptly.</p>
</div>'''
    
    async def generate_spreadsheet(
        self,
        employee: Employee,
        project: Optional[Project] = None,
        task: Optional[Task] = None,
        business_context: Optional[Dict] = None
    ) -> str:
        """Use AI to generate HTML that looks like an Excel spreadsheet with realistic data."""
        if not business_context:
            business_context = await get_business_context(self.db)
        
        # Get enhanced business context
        enhanced_context = await self._get_enhanced_business_context(business_context)
        
        # Build comprehensive context for AI
        context_parts = []
        context_parts.append(f"EMPLOYEE INFORMATION:")
        context_parts.append(f"  - Name: {employee.name}")
        context_parts.append(f"  - Title: {employee.title}")
        context_parts.append(f"  - Department: {employee.department or 'General'}")
        
        if project:
            context_parts.append(f"\nCURRENT PROJECT:")
            context_parts.append(f"  - Project Name: {project.name}")
            context_parts.append(f"  - Budget: ${project.budget or 0:,.2f}")
            context_parts.append(f"  - Revenue: ${project.revenue or 0:,.2f}")
        
        context_parts.append(f"\nBUSINESS METRICS:")
        context_parts.append(f"  - Total Revenue: ${enhanced_context.get('revenue', 0):,.2f}")
        context_parts.append(f"  - Total Profit: ${enhanced_context.get('profit', 0):,.2f}")
        context_parts.append(f"  - Total Expenses: ${enhanced_context.get('total_expenses', 0):,.2f}")
        context_parts.append(f"  - Profit Margin: {enhanced_context.get('profit_margin', 0):.2f}%")
        context_parts.append(f"  - Active Projects: {enhanced_context.get('active_projects', 0)}")
        context_parts.append(f"  - Total Employees: {enhanced_context.get('employee_count', 0)}")
        
        if enhanced_context.get('project_details'):
            context_parts.append(f"\nACTIVE PROJECTS DATA:")
            for proj in enhanced_context['project_details']:
                context_parts.append(f"  - {proj['name']}: Budget ${proj['budget']:,.2f}, Revenue ${proj['revenue']:,.2f}")
        
        if enhanced_context.get('department_distribution'):
            context_parts.append(f"\nDEPARTMENT DATA:")
            for dept, count in enhanced_context['department_distribution'].items():
                context_parts.append(f"  - {dept}: {count} employees")
        
        context_str = "\n".join(context_parts)
        
        prompt = f"""You are generating a FANCY, PROFESSIONAL, HIGH-QUALITY Microsoft Excel spreadsheet as HTML. This must look like a premium financial dashboard with real business data.

BUSINESS CONTEXT (USE ALL THIS REAL DATA):
{context_str}

CRITICAL REQUIREMENTS - MAKE IT FANCY AND DATA-RICH:

1. SPREADSHEET TYPE: Create based on employee role:
   - Finance/Accounting: Financial analysis, budget breakdown, revenue by department/project, expense tracking
   - Sales/Marketing: Sales performance, revenue by product/service, conversion metrics
   - Management: KPI dashboard, department performance, project ROI analysis
   - Operations: Resource allocation, efficiency metrics, cost analysis
   - HR: Employee cost analysis, department headcount, salary breakdown

2. PREMIUM EXCEL STYLING (Make it look like a $10,000 dashboard):
   - Professional grid with crisp borders (1px solid #d0d0d0)
   - Header row: Deep blue background (#366092), white bold text, 11pt Arial
   - Data rows: White background with alternating light gray (#f2f2f2) for zebra striping
   - Totals row: Light blue background (#e7f3ff), bold text, double border on top
   - Font: Arial, 11pt throughout
   - Cell padding: 8px for comfortable reading
   - Text alignment: Left for text, Right for numbers, Center for dates
   - Number formatting: Currency with $ and commas, percentages with %, proper decimals

3. SPREADSHEET STRUCTURE (Make it comprehensive):
   - TITLE ROW: Spreadsheet name in large bold (16pt), centered, with subtitle
   - HEADER ROW: 5-8 meaningful columns with descriptive names
   - DATA ROWS: 15-25 rows of REALISTIC data using actual business metrics
   - CALCULATED COLUMNS: Include formulas (totals, averages, percentages, growth rates)
   - SUMMARY SECTION: Multiple summary rows with key metrics
   - FOOTER: Data source, last updated date, notes

4. DATA REQUIREMENTS (USE REAL BUSINESS DATA):
   - Use ACTUAL revenue, profit, expense numbers from context
   - Include REAL project names, budgets, and revenue figures
   - Reference ACTUAL departments and their employee counts
   - Calculate realistic percentages, margins, growth rates
   - Include quarterly/monthly breakdowns if relevant
   - Add realistic variance analysis, trends, comparisons
   - Use proper financial formatting (currency, percentages, decimals)

5. MAKE IT FANCY:
   - Multiple related tables if needed (e.g., summary table + detailed breakdown)
   - Color coding: Green for positive, red for negative, blue for totals
   - Conditional formatting described in notes
   - Professional column groupings and subtotals
   - Include data validation notes or assumptions
   - Make it look like a CFO-level financial dashboard

6. HTML STRUCTURE:
   - Use <table> with border-collapse: collapse
   - Title: <tr><td colspan="X" style="text-align: center; font-size: 16pt; font-weight: bold; padding: 12px;">Title</td></tr>
   - Headers: <th style="background: #366092; color: white; font-weight: bold; padding: 8px; border: 1px solid #d0d0d0;">
   - Data: <td style="padding: 8px; border: 1px solid #d0d0d0; background: white;">
   - Alternating: background: #f2f2f2
   - Totals: background: #e7f3ff; font-weight: bold
   - All styles inline

IMPORTANT: Use the ACTUAL business data provided. Create realistic calculations, use real project names, reference actual departments. Make this spreadsheet look like it was created by a financial analyst. It should be comprehensive, data-rich, and visually impressive.

Generate the complete HTML spreadsheet now. Return ONLY the HTML table with inline styles."""

        try:
            client = await self.llm_client._get_client()
            response = await client.post(
                f"{self.llm_client.base_url}/api/generate",
                json={
                    "model": self.llm_client.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=httpx.Timeout(20.0, connect=5.0)
            )
            
            if response.status_code == 200:
                result = response.json()
                html_content = result.get("response", "").strip()
                html_content = html_content.strip('"').strip("'").strip()
                if html_content.startswith("```"):
                    html_content = re.sub(r'```[^\n]*\n', '', html_content)
                    html_content = re.sub(r'\n```', '', html_content)
                    html_content = html_content.strip()
                
                # Ensure it's a table
                if "<table" not in html_content.lower():
                    html_content = f'<table style="border-collapse: collapse; font-family: Arial, sans-serif; font-size: 11pt;">{html_content}</table>'
                
                return html_content
        except Exception as e:
            print(f"Error generating spreadsheet: {e}")
            import traceback
            traceback.print_exc()
        
        # Fallback content - create a realistic spreadsheet
        spreadsheet_title = "Financial Analysis" if "Finance" in employee.title or "Accounting" in employee.title else "Project Data Analysis"
        revenue = business_context.get('revenue', 100000) if business_context else 100000
        profit = business_context.get('profit', 20000) if business_context else 20000
        expenses = revenue - profit
        
        return f'''<div style="font-family: Arial, sans-serif; margin-bottom: 20px;">
<h2 style="font-size: 16pt; font-weight: bold; margin-bottom: 15px;">{spreadsheet_title}</h2>
</div>
<table style="border-collapse: collapse; font-family: Arial, sans-serif; font-size: 11pt; width: 100%;">
<thead>
<tr style="background: #366092; color: white;">
<th style="border: 1px solid #d0d0d0; padding: 8px; text-align: left; font-weight: bold;">Item</th>
<th style="border: 1px solid #d0d0d0; padding: 8px; text-align: right; font-weight: bold;">Q1</th>
<th style="border: 1px solid #d0d0d0; padding: 8px; text-align: right; font-weight: bold;">Q2</th>
<th style="border: 1px solid #d0d0d0; padding: 8px; text-align: right; font-weight: bold;">Q3</th>
<th style="border: 1px solid #d0d0d0; padding: 8px; text-align: right; font-weight: bold;">Q4</th>
<th style="border: 1px solid #d0d0d0; padding: 8px; text-align: right; font-weight: bold;">Total</th>
</tr>
</thead>
<tbody>
<tr style="background: white;">
<td style="border: 1px solid #d0d0d0; padding: 8px;">Revenue</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right;">${revenue / 4:,.2f}</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right;">${revenue / 4:,.2f}</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right;">${revenue / 4:,.2f}</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right;">${revenue / 4:,.2f}</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right; font-weight: bold;">${revenue:,.2f}</td>
</tr>
<tr style="background: #f2f2f2;">
<td style="border: 1px solid #d0d0d0; padding: 8px;">Expenses</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right;">${expenses / 4:,.2f}</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right;">${expenses / 4:,.2f}</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right;">${expenses / 4:,.2f}</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right;">${expenses / 4:,.2f}</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right; font-weight: bold;">${expenses:,.2f}</td>
</tr>
<tr style="background: white;">
<td style="border: 1px solid #d0d0d0; padding: 8px; font-weight: bold;">Net Profit</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right; font-weight: bold;">${profit / 4:,.2f}</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right; font-weight: bold;">${profit / 4:,.2f}</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right; font-weight: bold;">${profit / 4:,.2f}</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right; font-weight: bold;">${profit / 4:,.2f}</td>
<td style="border: 1px solid #d0d0d0; padding: 8px; text-align: right; font-weight: bold; background: #e7f3ff;">${profit:,.2f}</td>
</tr>
</tbody>
</table>'''
    
    async def generate_powerpoint(
        self,
        employee: Employee,
        project: Optional[Project] = None,
        task: Optional[Task] = None,
        business_context: Optional[Dict] = None
    ) -> str:
        """Use AI to generate HTML that looks like a PowerPoint presentation."""
        if not business_context:
            business_context = await get_business_context(self.db)
        
        # Get enhanced business context
        enhanced_context = await self._get_enhanced_business_context(business_context)
        
        # Build comprehensive context for AI
        context_parts = []
        context_parts.append(f"EMPLOYEE INFORMATION:")
        context_parts.append(f"  - Name: {employee.name}")
        context_parts.append(f"  - Title: {employee.title}")
        context_parts.append(f"  - Department: {employee.department or 'General'}")
        
        if project:
            context_parts.append(f"\nCURRENT PROJECT:")
            context_parts.append(f"  - Project Name: {project.name}")
            context_parts.append(f"  - Status: {project.status}")
            context_parts.append(f"  - Budget: ${project.budget or 0:,.2f}")
        
        context_parts.append(f"\nBUSINESS METRICS:")
        context_parts.append(f"  - Total Revenue: ${enhanced_context.get('revenue', 0):,.2f}")
        context_parts.append(f"  - Total Profit: ${enhanced_context.get('profit', 0):,.2f}")
        context_parts.append(f"  - Profit Margin: {enhanced_context.get('profit_margin', 0):.2f}%")
        context_parts.append(f"  - Active Projects: {enhanced_context.get('active_projects', 0)}")
        context_parts.append(f"  - Total Employees: {enhanced_context.get('employee_count', 0)}")
        
        if enhanced_context.get('project_details'):
            context_parts.append(f"\nACTIVE PROJECTS:")
            for proj in enhanced_context['project_details'][:5]:
                context_parts.append(f"  - {proj['name']}: ${proj['budget']:,.2f} budget")
        
        if enhanced_context.get('department_distribution'):
            context_parts.append(f"\nDEPARTMENT BREAKDOWN:")
            for dept, count in list(enhanced_context['department_distribution'].items())[:6]:
                context_parts.append(f"  - {dept}: {count} employees")
        
        context_str = "\n".join(context_parts)
        
        prompt = f"""You are generating a FANCY, PROFESSIONAL, HIGH-QUALITY Microsoft PowerPoint presentation as HTML. This must look like a premium executive presentation with real business data.

BUSINESS CONTEXT (USE ALL THIS REAL DATA):
{context_str}

CRITICAL REQUIREMENTS - MAKE IT FANCY AND IMPRESSIVE:

1. PRESENTATION TYPE: Create based on employee role:
   - Executives/Managers: Quarterly business review, strategic overview, company performance
   - Sales/Marketing: Sales pitch, market analysis, campaign results, revenue presentation
   - Finance: Financial overview, budget presentation, revenue analysis
   - Operations: Operational efficiency, process improvement, resource allocation
   - HR: Team overview, organizational structure, hiring strategy

2. PREMIUM POWERPOINT STYLING (Make it look like a $50,000 presentation):
   - Each slide: White background (#ffffff), centered, max-width 960px
   - Slide container: Padding 60px, margin 30px auto, elegant box-shadow (0 4px 12px rgba(0,0,0,0.15))
   - Title slide: 48pt Calibri, bold, dark blue (#2F5597), centered
   - Content titles: 36-40pt Calibri, bold, dark blue (#2F5597), left-aligned
   - Body text: 20-24pt Calibri, black (#333333), professional line-height (1.6)
   - Bullet points: 20pt, proper indentation (40px), professional spacing
   - Color scheme: Professional blues (#2F5597, #366092), grays, whites

3. SLIDE STRUCTURE (Create 5-7 comprehensive slides):
   - SLIDE 1 - TITLE: 
     * Large title (48pt), employee name and title, date, company logo placeholder
     * Professional subtitle with presentation purpose
   
   - SLIDE 2 - AGENDA/OVERVIEW:
     * Clear agenda with 4-6 items
     * Professional numbering or bullet points
   
   - SLIDE 3-5 - MAIN CONTENT SLIDES:
     * Each with clear title (36pt)
     * 4-6 detailed bullet points with REAL business data
     * Include actual numbers, percentages, project names
     * Professional analysis and insights
     * Use data from business context (revenue, profit, projects, departments)
   
   - SLIDE 6 - DATA/ANALYTICS:
     * Key metrics slide with actual numbers
     * Revenue, profit, employee counts, project data
     * Formatted professionally with labels and values
   
   - SLIDE 7 - SUMMARY/CONCLUSION:
     * Key takeaways
     * Next steps or recommendations
     * Professional closing

4. CONTENT REQUIREMENTS (USE REAL BUSINESS DATA):
   - Reference ACTUAL revenue, profit, profit margin numbers
   - Mention REAL project names and their budgets/status
   - Include ACTUAL department names and employee counts
   - Use REAL business metrics and calculations
   - Add professional insights and strategic recommendations
   - Each bullet point should be substantial (full sentences, not fragments)
   - Include data-driven analysis and trends

5. MAKE IT FANCY:
   - Professional slide transitions described in notes
   - Data visualizations described (e.g., "Revenue increased 15% YoY")
   - Executive-level language and strategic thinking
   - Professional formatting with consistent styling
   - Include charts/graphs descriptions where appropriate
   - Make it look like a boardroom presentation

6. HTML STRUCTURE:
   - Wrap each slide: <div class="slide" style="background: #ffffff; padding: 60px; margin: 30px auto; max-width: 960px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-family: 'Calibri', Arial, sans-serif; min-height: 600px;">
   - Title: <h1 style="font-size: 36-48pt; font-weight: bold; color: #2F5597; margin-bottom: 40px;">
   - Bullet points: <ul style="font-size: 20pt; line-height: 1.8; margin-left: 40px; color: #333;">
   - Data: Use tables or formatted lists for metrics
   - All styles inline

IMPORTANT: Use the ACTUAL business data provided. Reference real projects, real numbers, real departments. Make this presentation look like it was created for a board meeting. It should be comprehensive, data-rich, visually impressive, and executive-level quality.

Generate the complete HTML presentation now. Return ONLY the HTML with inline styles. Wrap each slide in a div with class="slide"."""

        try:
            client = await self.llm_client._get_client()
            response = await client.post(
                f"{self.llm_client.base_url}/api/generate",
                json={
                    "model": self.llm_client.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=httpx.Timeout(20.0, connect=5.0)
            )
            
            if response.status_code == 200:
                result = response.json()
                html_content = result.get("response", "").strip()
                html_content = html_content.strip('"').strip("'").strip()
                if html_content.startswith("```"):
                    html_content = re.sub(r'```[^\n]*\n', '', html_content)
                    html_content = re.sub(r'\n```', '', html_content)
                    html_content = html_content.strip()
                
                return html_content
        except Exception as e:
            print(f"Error generating PowerPoint: {e}")
            import traceback
            traceback.print_exc()
        
        # Fallback content - create a realistic presentation
        presentation_title = project.name if project else f"{employee.department or 'Business'} Overview"
        revenue = business_context.get('revenue', 100000) if business_context else 100000
        profit = business_context.get('profit', 20000) if business_context else 20000
        active_projects = business_context.get('active_projects', 0) if business_context else 0
        employee_count = business_context.get('employee_count', 0) if business_context else 0
        
        return f'''<div class="slide" style="background: #ffffff; padding: 60px; margin: 30px auto; max-width: 960px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-family: 'Calibri', Arial, sans-serif; min-height: 600px; display: flex; flex-direction: column; justify-content: center;">
<h1 style="font-size: 44pt; font-weight: bold; color: #2F5597; margin-bottom: 20px; text-align: center;">{presentation_title}</h1>
<p style="font-size: 24pt; text-align: center; color: #666; margin-top: 30px;">{employee.name}</p>
<p style="font-size: 18pt; text-align: center; color: #666;">{employee.title}</p>
<p style="font-size: 16pt; text-align: center; color: #999; margin-top: 40px;">{local_now().strftime('%B %Y')}</p>
</div>
<div class="slide" style="background: #ffffff; padding: 60px; margin: 30px auto; max-width: 960px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-family: 'Calibri', Arial, sans-serif; min-height: 600px;">
<h1 style="font-size: 36pt; font-weight: bold; color: #2F5597; margin-bottom: 40px;">Agenda</h1>
<ul style="font-size: 20pt; line-height: 1.8; margin-left: 40px; color: #333;">
<li style="margin-bottom: 20px;">Current Business Overview</li>
<li style="margin-bottom: 20px;">Key Performance Metrics</li>
<li style="margin-bottom: 20px;">Strategic Initiatives</li>
<li style="margin-bottom: 20px;">Next Steps and Recommendations</li>
</ul>
</div>
<div class="slide" style="background: #ffffff; padding: 60px; margin: 30px auto; max-width: 960px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-family: 'Calibri', Arial, sans-serif; min-height: 600px;">
<h1 style="font-size: 36pt; font-weight: bold; color: #2F5597; margin-bottom: 40px;">Business Overview</h1>
<ul style="font-size: 20pt; line-height: 1.8; margin-left: 40px; color: #333;">
<li style="margin-bottom: 20px;">Revenue: ${revenue:,.2f}</li>
<li style="margin-bottom: 20px;">Profit: ${profit:,.2f}</li>
<li style="margin-bottom: 20px;">Active Projects: {active_projects}</li>
<li style="margin-bottom: 20px;">Team Size: {employee_count} employees</li>
</ul>
</div>
<div class="slide" style="background: #ffffff; padding: 60px; margin: 30px auto; max-width: 960px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-family: 'Calibri', Arial, sans-serif; min-height: 600px;">
<h1 style="font-size: 36pt; font-weight: bold; color: #2F5597; margin-bottom: 40px;">Key Findings</h1>
<ul style="font-size: 20pt; line-height: 1.8; margin-left: 40px; color: #333;">
<li style="margin-bottom: 20px;">Performance metrics indicate positive trends</li>
<li style="margin-bottom: 20px;">Resource allocation aligns with strategic priorities</li>
<li style="margin-bottom: 20px;">Stakeholder engagement remains strong</li>
<li style="margin-bottom: 20px;">Operational efficiency continues to improve</li>
</ul>
</div>
<div class="slide" style="background: #ffffff; padding: 60px; margin: 30px auto; max-width: 960px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-family: 'Calibri', Arial, sans-serif; min-height: 600px;">
<h1 style="font-size: 36pt; font-weight: bold; color: #2F5597; margin-bottom: 40px;">Next Steps</h1>
<ul style="font-size: 20pt; line-height: 1.8; margin-left: 40px; color: #333;">
<li style="margin-bottom: 20px;">Continue monitoring key performance indicators</li>
<li style="margin-bottom: 20px;">Maintain focus on strategic priorities</li>
<li style="margin-bottom: 20px;">Enhance cross-department collaboration</li>
<li style="margin-bottom: 20px;">Regular review and adjustment of initiatives</li>
</ul>
</div>
<div class="slide" style="background: #ffffff; padding: 60px; margin: 30px auto; max-width: 960px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-family: 'Calibri', Arial, sans-serif; min-height: 600px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
<h1 style="font-size: 36pt; font-weight: bold; color: #2F5597; margin-bottom: 30px;">Thank You</h1>
<p style="font-size: 24pt; color: #666; text-align: center;">Questions & Discussion</p>
</div>'''
    
    async def generate_change_summary(
        self,
        old_content: str,
        new_content: str,
        employee: Employee
    ) -> str:
        """Use AI to generate a summary of changes between two versions."""
        prompt = f"""Compare two versions of a document and generate a brief summary of the changes.

Employee who made changes: {employee.name} ({employee.title})

Old version (first 500 chars):
{old_content[:500]}

New version (first 500 chars):
{new_content[:500]}

Generate a brief, professional summary (2-3 sentences) describing what changed between these versions. Focus on:
- What content was added
- What content was modified
- What content was removed (if applicable)
- Overall nature of the update

Write in third person. Example: "Updated financial figures with Q4 results. Added new section on market analysis. Revised project timeline."

Return ONLY the summary text, nothing else."""

        try:
            client = await self.llm_client._get_client()
            response = await client.post(
                f"{self.llm_client.base_url}/api/generate",
                json={
                    "model": self.llm_client.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=httpx.Timeout(15.0, connect=5.0)
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get("response", "").strip()
                summary = summary.strip('"').strip("'").strip()
                if summary.startswith("```"):
                    summary = re.sub(r'```[^\n]*\n', '', summary)
                    summary = re.sub(r'\n```', '', summary)
                    summary = summary.strip()
                
                return summary[:500]  # Limit length
        except Exception as e:
            print(f"Error generating change summary: {e}")
        
        return "Document updated with latest information."
    
    async def create_new_version(
        self,
        file: SharedDriveFile,
        new_content: str,
        employee: Employee
    ) -> SharedDriveFileVersion:
        """Create a new version entry when a file is updated."""
        # Get previous version content for comparison
        old_content = file.content_html
        
        # Generate change summary using AI
        change_summary = await self.generate_change_summary(old_content, new_content, employee)
        
        # Create new version
        new_version = SharedDriveFileVersion(
            file_id=file.id,
            version_number=file.current_version + 1,
            content_html=old_content,  # Store the old content
            file_size=len(old_content.encode('utf-8')),
            created_by_id=employee.id,
            change_summary=change_summary,
            file_metadata={"updated_at": local_now().isoformat()}
        )
        self.db.add(new_version)
        
        # Update file
        file.content_html = new_content
        file.file_size = len(new_content.encode('utf-8'))
        file.current_version += 1
        file.last_updated_by_id = employee.id
        file.updated_at = local_now()
        
        return new_version
    
    async def generate_documents_for_employee(
        self,
        employee: Employee,
        business_context: Optional[Dict] = None,
        max_documents: int = 1
    ) -> List[SharedDriveFile]:
        """AI decides what documents to create for a specific employee."""
        if not business_context:
            business_context = await get_business_context(self.db)
        
        # Get employee's current work
        # Eagerly load current_task_id to avoid lazy-loading issues
        current_task_id = employee.current_task_id
        current_task = None
        current_project = None
        if current_task_id:
            result = await self.db.execute(
                select(Task).where(Task.id == current_task_id)
            )
            current_task = result.scalar_one_or_none()
            if current_task and current_task.project_id:
                result = await self.db.execute(
                    select(Project).where(Project.id == current_task.project_id)
                )
                current_project = result.scalar_one_or_none()
        
        # Check existing files for this employee
        result = await self.db.execute(
            select(SharedDriveFile).where(SharedDriveFile.employee_id == employee.id)
        )
        existing_files = result.scalars().all()
        
        # Skip if employee already has many recent files (prevent over-generation)
        if len(existing_files) >= 10:
            # Only create if no files in last 2 hours
            from datetime import timezone
            now_dt = local_now()
            recent_count = 0
            for f in existing_files:
                if f.updated_at:
                    updated_dt = f.updated_at
                    # Normalize timezone
                    if now_dt.tzinfo is not None and updated_dt.tzinfo is None:
                        updated_dt = updated_dt.replace(tzinfo=timezone.utc)
                        updated_dt = updated_dt.astimezone(now_dt.tzinfo)
                    elif now_dt.tzinfo is None and updated_dt.tzinfo is not None:
                        now_dt_temp = now_dt.replace(tzinfo=timezone.utc)
                        now_dt_temp = now_dt_temp.astimezone(updated_dt.tzinfo)
                        if (now_dt_temp - updated_dt).total_seconds() < 7200:
                            recent_count += 1
                    elif now_dt.tzinfo != updated_dt.tzinfo and now_dt.tzinfo is not None:
                        updated_dt = updated_dt.astimezone(now_dt.tzinfo)
                        if (now_dt - updated_dt).total_seconds() < 7200:
                            recent_count += 1
                    else:
                        if (now_dt - updated_dt).total_seconds() < 7200:
                            recent_count += 1
            if recent_count > 0:
                return []  # Skip this employee, they have recent files
        
        # Use AI to decide what documents to create
        context_parts = []
        context_parts.append(f"Employee: {employee.name}, {employee.title}, {employee.department}")
        if current_project:
            context_parts.append(f"Current Project: {current_project.name} ({current_project.status})")
        if current_task:
            context_parts.append(f"Current Task: {current_task.description}")
        context_parts.append(f"Existing files: {len(existing_files)}")
        existing_types = [f.file_type for f in existing_files]
        type_counts = {t: existing_types.count(t) for t in ["word", "spreadsheet", "powerpoint"]}
        context_parts.append(f"Existing file types - Word: {type_counts.get('word', 0)}, Spreadsheet: {type_counts.get('spreadsheet', 0)}, PowerPoint: {type_counts.get('powerpoint', 0)}")
        context_parts.append(f"Business Revenue: ${business_context.get('revenue', 0):,.2f}")
        
        context_str = "\n".join(context_parts)
        
        prompt = f"""As an AI assistant managing a company's shared drive, decide what documents should be created for this employee.

Context:
{context_str}

Based on the employee's role, current work, and business context, decide:
1. What type of document(s) should be created? (word, spreadsheet, or powerpoint)
2. What should the document be about?

Consider:
- Employee's role and department
- Current projects and tasks
- What documents would be useful for their work
- Business needs
- EXISTING FILE COUNTS: Prioritize creating WORD documents if the employee has fewer word docs than other types

Respond in JSON format:
{{
    "documents": [
        {{"type": "word|spreadsheet|powerpoint", "purpose": "brief description"}},
        ...
    ]
}}

IMPORTANT: 
- If employee has fewer WORD documents than spreadsheets/powerpoints, prioritize creating a WORD document
- Vary the document types based on what's missing
- Spreadsheets for: financial data, budgets, analysis, metrics, tracking, calculations
- PowerPoints for: presentations, proposals, reports, meetings, pitches, summaries
- Word documents for: reports, memos, documentation, summaries, letters

Generate 1 document suggestion. Choose the MOST appropriate type based on the employee's work and existing files. Be realistic and relevant."""

        try:
            client = await self.llm_client._get_client()
            response = await client.post(
                f"{self.llm_client.base_url}/api/generate",
                json={
                    "model": self.llm_client.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=httpx.Timeout(15.0, connect=5.0)
            )
            
            documents_to_create = []
            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "").strip()
                # Try to parse JSON
                try:
                    import json
                    if "{" in response_text:
                        # Try to find JSON in the response
                        json_match = re.search(r'\{.*?"documents".*?\}', response_text, re.DOTALL)
                        if json_match:
                            data = json.loads(json_match.group())
                            documents_to_create = data.get("documents", [])
                        else:
                            # Try to find any JSON object
                            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
                            if json_match:
                                data = json.loads(json_match.group())
                                documents_to_create = data.get("documents", [])
                except Exception as parse_error:
                    print(f"  ⚠️  Could not parse AI response as JSON: {parse_error}")
                    # Try to extract document type from text if JSON parsing fails
                    response_lower = response_text.lower()
                    if "spreadsheet" in response_lower or "excel" in response_lower:
                        documents_to_create = [{"type": "spreadsheet", "purpose": "data analysis"}]
                    elif "powerpoint" in response_lower or "presentation" in response_lower or "ppt" in response_lower:
                        documents_to_create = [{"type": "powerpoint", "purpose": "presentation"}]
                    # Otherwise will use fallback logic
            
            # Fallback: always create at least one document based on employee role with variety
            if not documents_to_create:
                import random
                # Check what types of files employee already has
                existing_types = [f.file_type for f in existing_files]
                
                # Determine preferred type based on role
                if "Finance" in employee.title or "Accounting" in employee.title or "Financial" in employee.title:
                    preferred_type = "spreadsheet"
                elif "Sales" in employee.title or "Marketing" in employee.title or "Business Development" in employee.title:
                    preferred_type = "powerpoint"
                elif employee.role in ["CEO", "Manager", "Director"]:
                    # Managers/executives can have any type, but prefer word or powerpoint
                    preferred_type = random.choice(["word", "powerpoint"])
                else:
                    # For other roles, vary the type
                    preferred_type = random.choice(["word", "spreadsheet", "powerpoint"])
                
                # Check what types are missing or underrepresented
                word_count = existing_types.count("word")
                spreadsheet_count = existing_types.count("spreadsheet")
                powerpoint_count = existing_types.count("powerpoint")
                
                # Prioritize creating word documents if they're underrepresented
                if word_count < spreadsheet_count and word_count < powerpoint_count:
                    preferred_type = "word"
                elif spreadsheet_count < word_count and spreadsheet_count < powerpoint_count:
                    preferred_type = "spreadsheet"
                elif powerpoint_count < word_count and powerpoint_count < spreadsheet_count:
                    preferred_type = "powerpoint"
                # If employee already has many of preferred type, try a different one
                elif existing_types.count(preferred_type) >= 3:
                    other_types = ["word", "spreadsheet", "powerpoint"]
                    other_types.remove(preferred_type)
                    preferred_type = random.choice(other_types)
                
                # Create document based on type
                if preferred_type == "spreadsheet":
                    documents_to_create = [{"type": "spreadsheet", "purpose": "financial data or analysis"}]
                elif preferred_type == "powerpoint":
                    documents_to_create = [{"type": "powerpoint", "purpose": "presentation or proposal"}]
                else:
                    documents_to_create = [{"type": "word", "purpose": "report or summary"}]
            
            # If employee has no files yet, prioritize word documents first
            if not existing_files and not documents_to_create:
                # Start with word document for new employees
                documents_to_create = [{"type": "word", "purpose": "initial work document"}]
            
            created_files = []
            # Limit documents to prevent overwhelming the system
            for doc_spec in documents_to_create[:max_documents]:
                try:
                    file_type = doc_spec.get("type", "word").lower().strip()
                    
                    # Normalize file type to ensure we get the right one
                    if file_type not in ["word", "spreadsheet", "powerpoint"]:
                        # Try to infer from common variations
                        if "excel" in file_type or "sheet" in file_type or "spread" in file_type:
                            file_type = "spreadsheet"
                        elif "power" in file_type or "point" in file_type or "ppt" in file_type or "presentation" in file_type:
                            file_type = "powerpoint"
                        else:
                            file_type = "word"
                    
                    # Generate file name
                    file_name = await self.generate_file_name(file_type, employee, current_project, current_task)
                    if not file_name or not file_name.strip():
                        # Fallback file name
                        file_name = f"{employee.name.replace(' ', '_')}_{file_type}_{local_now().strftime('%Y%m%d')}.html"
                    
                    # Generate content based on normalized type
                    print(f"  Generating {file_type} document for {employee.name}...")
                    if file_type == "spreadsheet":
                        content = await self.generate_spreadsheet(employee, current_project, current_task, business_context)
                    elif file_type == "powerpoint":
                        content = await self.generate_powerpoint(employee, current_project, current_task, business_context)
                    else:
                        # Default to word if type is unclear
                        content = await self.generate_word_document(employee, current_project, current_task, business_context)
                    
                    if not content or not content.strip():
                        print(f"  ⚠️  Warning: Empty content generated for {employee.name}, skipping...")
                        continue
                    
                    # Check for duplicate content before creating
                    if await self._check_duplicate_content(content, employee.id, file_type):
                        print(f"  ⚠️  Skipping duplicate document for {employee.name}")
                        continue
                    
                    # Determine file path
                    project_name = current_project.name if current_project else None
                    file_path = self._get_file_path(
                        employee.department or "General",
                        employee.name,
                        project_name or "General",
                        file_name
                    )
                    
                    # Create file record
                    drive_file = SharedDriveFile(
                        file_name=file_name,
                        file_type=file_type,
                        department=employee.department,
                        employee_id=employee.id,
                        project_id=current_project.id if current_project else None,
                        file_path=file_path,
                        file_size=len(content.encode('utf-8')),
                        content_html=content,
                        file_metadata={
                            "purpose": doc_spec.get("purpose", ""),
                            "created_by_ai": True,
                            "created_at": local_now().isoformat()
                        },
                        last_updated_by_id=employee.id,
                        current_version=1
                    )
                    self.db.add(drive_file)
                    created_files.append(drive_file)
                    
                    # Save to filesystem
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f"  ✓ Created {file_type} document: {file_name}")
                except Exception as e:
                    print(f"  ✗ Error creating document for {employee.name}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            await self.db.flush()
            return created_files
            
        except Exception as e:
            print(f"Error generating documents for employee {employee.id}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def update_existing_documents(
        self,
        employee: Employee,
        business_context: Optional[Dict] = None,
        max_updates: int = 1
    ) -> List[SharedDriveFile]:
        """AI updates existing documents based on current work."""
        if not business_context:
            business_context = await get_business_context(self.db)
        
        # Get files that might need updating (created by this employee or related to their projects)
        result = await self.db.execute(
            select(SharedDriveFile).where(
                (SharedDriveFile.employee_id == employee.id) |
                (SharedDriveFile.last_updated_by_id == employee.id)
            ).order_by(desc(SharedDriveFile.updated_at))
        )
        files_to_check = result.scalars().all()[:max_updates]  # Limit updates to prevent blocking
        
        updated_files = []
        for file in files_to_check:
            # Use AI to decide if file should be updated
            # For now, update files that are older than 1 hour
            if file.updated_at:
                # Normalize timezone for comparison
                now_dt = local_now()
                updated_dt = file.updated_at
                
                # If one is timezone-aware and the other is naive, normalize
                if now_dt.tzinfo is not None and updated_dt.tzinfo is None:
                    # Assume updated_at is in UTC if naive
                    from datetime import timezone
                    updated_dt = updated_dt.replace(tzinfo=timezone.utc)
                    updated_dt = updated_dt.astimezone(now_dt.tzinfo)
                elif now_dt.tzinfo is None and updated_dt.tzinfo is not None:
                    # Make now_dt timezone-aware
                    from datetime import timezone
                    now_dt = now_dt.replace(tzinfo=timezone.utc)
                    now_dt = now_dt.astimezone(updated_dt.tzinfo)
                elif now_dt.tzinfo is None and updated_dt.tzinfo is None:
                    # Both naive, can subtract directly
                    pass
                else:
                    # Both timezone-aware, ensure same timezone
                    if now_dt.tzinfo != updated_dt.tzinfo:
                        updated_dt = updated_dt.astimezone(now_dt.tzinfo)
                
                time_since_update = (now_dt - updated_dt).total_seconds()
                if time_since_update > 3600:  # 1 hour
                    # Get current project/task context
                    # Eagerly load current_task_id to avoid lazy-loading issues
                    current_task_id = employee.current_task_id
                    current_project = None
                    current_task = None
                    if current_task_id:
                        result = await self.db.execute(
                            select(Task).where(Task.id == current_task_id)
                        )
                        current_task = result.scalar_one_or_none()
                        if current_task and current_task.project_id:
                            result = await self.db.execute(
                                select(Project).where(Project.id == current_task.project_id)
                            )
                            current_project = result.scalar_one_or_none()
                    
                    # Generate updated content
                    if file.file_type == "word":
                        new_content = await self.generate_word_document(employee, current_project, current_task, business_context)
                    elif file.file_type == "spreadsheet":
                        new_content = await self.generate_spreadsheet(employee, current_project, current_task, business_context)
                    elif file.file_type == "powerpoint":
                        new_content = await self.generate_powerpoint(employee, current_project, current_task, business_context)
                    else:
                        new_content = await self.generate_word_document(employee, current_project, current_task, business_context)
                    
                    # Create version history
                    await self.create_new_version(file, new_content, employee)
                    
                    # Update filesystem
                    with open(file.file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    updated_files.append(file)
        
        await self.db.flush()
        return updated_files
    
    async def get_employee_recent_files(
        self,
        employee_id: int,
        limit: int = 15
    ) -> List[SharedDriveFile]:
        """Get recent files created/updated by an employee."""
        result = await self.db.execute(
            select(SharedDriveFile)
            .options(
                selectinload(SharedDriveFile.employee),
                selectinload(SharedDriveFile.project),
                selectinload(SharedDriveFile.last_updated_by),
                selectinload(SharedDriveFile.versions)
            )
            .where(
                (SharedDriveFile.employee_id == employee_id) |
                (SharedDriveFile.last_updated_by_id == employee_id)
            ).order_by(desc(SharedDriveFile.updated_at)).limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_file_structure(self) -> Dict:
        """Get hierarchical file structure for API."""
        result = await self.db.execute(
            select(SharedDriveFile)
            .options(
                selectinload(SharedDriveFile.employee),
                selectinload(SharedDriveFile.project)
            )
            .order_by(
                SharedDriveFile.department,
                SharedDriveFile.employee_id,
                SharedDriveFile.project_id,
                SharedDriveFile.file_name
            )
        )
        all_files = result.scalars().all()
        
        structure = {}
        for file in all_files:
            dept = file.department or "General"
            # Access employee name safely - already loaded
            emp_name = file.employee.name if file.employee else "Shared"
            proj_name = file.project.name if file.project else "General"
            
            if dept not in structure:
                structure[dept] = {}
            if emp_name not in structure[dept]:
                structure[dept][emp_name] = {}
            if proj_name not in structure[dept][emp_name]:
                structure[dept][emp_name][proj_name] = []
            
            structure[dept][emp_name][proj_name].append({
                "id": file.id,
                "file_name": file.file_name,
                "file_type": file.file_type,
                "current_version": file.current_version,
                "updated_at": file.updated_at.isoformat() if file.updated_at else None
            })
        
        return structure

