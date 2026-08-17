# FILE-BY-FILE BREAKDOWN
## What Each File Does (Quick Reference)

---

## 📁 BACKEND FILES (Python - Data Processing)

### `backend/app.py` - Main Server
```
Purpose: Heart of the system. Receives requests, runs 5-agent pipeline, returns results.

What it does:
  1. Start Flask server on port 5000
  2. Set up CORS (allow Angular frontend to talk to it)
  3. Initialize all 5 agents
  4. Create routes:
     - /api/validate (main endpoint)
     - /api/health (status check)
     - /ui/* (serve Angular UI)

Key code:
  @app.route('/api/validate', methods=['POST'])
  def validate_assessment():
      intake_result = intake_agent.process(request_data)      # Agent 1
      classification = classifier_agent.process(intake_result) # Agent 2
      issues = validator_agent.process(intake_result)         # Agent 3
      corrected = correction_agent.process(issues, ...)       # Agent 4
      report = report_agent.process(...)                      # Agent 5
      return jsonify(report)

Why this structure?
  - Single entry point for all requests
  - Orchestrates the 5-agent pipeline
  - Handles errors gracefully
  - Logs every step (audit trail)

Testing:
  curl -X POST http://localhost:5000/api/validate \
    -H "Content-Type: application/json" \
    -d @sample_request.json
```

---

### `backend/agents/intake_agent.py` - Agent 1
```
Purpose: Parse raw messy data, organize into clean structure.

What it does:
  INPUT: Raw JSON from Angular browser
    {
      "submission": { user answers },
      "template": { validation rules }
    }
  
  PROCESSING:
    1. Extract member info (MemberId, StateID)
    2. Extract answers (pages → questions → values)
    3. Extract template rules (pages → questions → validation rules)
    4. Build fast lookup tables (dictionaries)
  
  OUTPUT: IntakeContext (structured dict)
    {
      "member_id": "9652320756",
      "submitted_answers": { "Q1": "Yes", ... },  ← Fast O(1) lookup
      "template_questions": { "Q1": {...rules...}, ... },  ← Fast lookup
      "conditional_rules": [...]
    }

Why this structure?
  - Transforms "browser format" to "validation format"
  - Builds lookup tables for fast searches
  - Separates data extraction from validation
  - Makes code reusable

Key insight:
  Agent 1 does: Parse once, validate many times
  If Agent 1 fails → Immediately return error (don't waste time)
  If Agent 1 succeeds → All other agents have structured data
```

---

### `backend/agents/classifier_agent.py` - Agent 2
```
Purpose: Classify error type, route to right team.

What it does:
  INPUT: IntakeContext from Agent 1
  
  CHECKS:
    1. System Issue? (timeout, connection error)
       → YES: Escalate to Infrastructure Team
       → NO: Continue
    
    2. Template Issue? (wrong # of questions)
       → YES: Escalate to Engineering Team
       → NO: Continue
    
    3. Missing Template?
       → YES: Escalate
       → NO: Continue
  
  OUTPUT: Classification result
    {
      "error_type": "UserError" | "TemplateIssue" | "SystemIssue",
      "escalate": True | False,
      "routed_to": "Care Manager" | "Engineering" | "Infra"
    }

Why this structure?
  - Triage early (don't validate bad data)
  - Clear routing (who fixes what?)
  - Prevents wasted effort on impossible tasks
  - Healthcare analogy: ER triage nurse

Key insight:
  If escalate=True → STOP here, skip to Agent 5 (Report)
  If escalate=False → Continue to Agent 3 (Validate)
```

---

### `backend/agents/format_validator.py` - Agent 3
```
Purpose: THE CORE VALIDATOR - Catches 90-95% of errors.

What it does:
  INPUT: IntakeContext from Agent 1
  
  VALIDATES: 8 types of issues
    1. Required field empty
    2. Question in template but not answered
    3. Invalid date format
    4. Non-numeric in number field
    5. Button group value not in valid options
    6. Text too long (exceeds max length)
    7. Conditional rule violated (if Q1=Yes, Q2 required)
    8. Textblock question has answer (shouldn't)
  
  OUTPUT: List of issues found
    [
      {
        "questionId": "Q2",
        "errorType": "InvalidDateFormat",
        "originalValue": "01/15/2024",
        "description": "Expected YYYY-MM-DD format"
      },
      ...
    ]

Why this structure?
  - NO AI (deterministic, rules-based)
  - Fast (no API calls)
  - Catches 90-95% of errors
  - Highly auditable (clear logic)

Key insight:
  This is the "assembly line quality inspector"
  Every question → check against rules
  Issues → list them, don't fix yet
```

---

### `backend/agents/correction_agent.py` - Agent 4
```
Purpose: Auto-fix common errors, suggest AI improvements.

What it does:
  INPUT: Issues list from Agent 3
  
  TIER 1: Deterministic Auto-Fix (No AI, 100% safe)
    - Numeric: Remove whitespace " 95 " → "95"
    - Date: Convert format "01/15/2024" → "2024-01-15"
    - Text: Trim spaces "  comment  " → "comment"
  
  TIER 2: AI-Powered Suggestions (Uses OpenRouter → GPT-4o)
    - Only for clinical text fields (comments, rationale, etc)
    - Suggest improved wording
    - Mark as autoFixed=False (needs review)
  
  OUTPUT: (updated_issues, corrected_answers)
    {
      "Q2": {"autoFixed": True, "correctedValue": "2024-01-15"},
      "Q44": {"autoFixed": True, "correctedValue": "95"},
      "Q50": {"autoFixed": False, "suggestion": "Better wording..."}
    }

Why this structure?
  - Tier 1: Safe, instant, free
  - Tier 2: Careful, costs money, needs review
  - Two-tier approach → Best of both worlds

Key insight:
  autoFixed=True → Care manager MUST accept (format correction)
  autoFixed=False → Care manager CAN choose to accept (suggestion)
```

---

### `backend/agents/report_agent.py` - Agent 5
```
Purpose: Assemble all results into final response.

What it does:
  INPUT: intake_context, issues, corrected_answers, ...
  
  PROCESSING:
    1. Count issue types
       - total_issues = len(issues)
       - auto_fixed_count = sum of autoFixed=True
       - needs_review_count = sum of autoFixed=False
    
    2. Determine status
       - "pass" (no issues)
       - "pass_with_fixes" (auto-fixed everything)
       - "review_needed" (human must review some)
       - "error" (critical issues)
    
    3. Write summary
       "3 issues auto-fixed, 1 needs review"
    
    4. Build corrected submission
       Original answers + auto-fixed answers
       Ready to save to database
  
  OUTPUT: Final response JSON
    {
      "status": "review_needed",
      "summary": "3 auto-fixed, 1 needs review",
      "totalIssues": 4,
      "autoFixedCount": 3,
      "needsReviewCount": 1,
      "issues": [...],
      "correctedSubmission": {...}
    }

Why this structure?
  - Consolidates all agent outputs
  - Makes decision on status
  - Provides care manager-friendly summary
  - Returns corrected submission ready to save

Key insight:
  This is what care manager sees in the browser
  Clear, actionable, ready to save
```

---

### `backend/services/ai_service.py` - AI Integration
```
Purpose: Handle all communication with OpenRouter API (GPT-4o).

What it does:
  INPUT: Prompt (question to ask AI)
  
  CALLS: OpenRouter API
    POST https://openrouter.ai/api/v1/chat/completions
    with {
      "model": "openai/gpt-4o",
      "messages": [{"role": "user", "content": prompt}],
      "temperature": 0.7,
      "max_tokens": 150
    }
  
  OUTPUT: AI response OR mock response if API fails
  
  SECURITY:
    - Never sends PHI (patient data)
    - Only sends: field name + context
    - Example prompt:
      "Clinical Summary field: {description}
       Member has mobility issues: Yes
       Current: 'Member ok'
       Suggest improvement: "

Why this structure?
  - Centralized AI integration (change one place)
  - Fallback mechanism (if API fails, use mock)
  - HIPAA compliant (no PHI sent)
  - Cost tracking (can log API calls)

Key insight:
  This is the ONLY place that talks to AI
  If you want to switch from GPT-4o to Claude: Change one line
```

---

### `backend/requirements.txt` - Python Dependencies
```
Purpose: List all Python packages needed to run the system.

Contents:
  flask==3.1.0              # Web framework
  flask-cors==5.0.0         # Allow browser requests
  python-dotenv==1.1.0      # Load environment variables
  requests==2.32.3          # Make HTTP calls to OpenRouter API

Why this file?
  - Reproducible deployments (same versions everywhere)
  - Easy setup (pip install -r requirements.txt)
  - Clear dependencies (easy to audit)

Minimal dependencies by design:
  - Only essential packages
  - No bloat
  - Easy to maintain
```

---

## 🌐 FRONTEND FILES (Angular/TypeScript - User Interface)

### `frontend/src/app/app.component.ts` - Main Component Logic
```
Purpose: Core Angular component. Manages UI state, handles user interactions.

What it does:
  PROPERTIES (UI State):
    isValidating: Boolean    ← Show loading spinner?
    showModal: Boolean       ← Show results modal?
    validationResponse: Data ← Results to display
    validationError: String  ← Error message
  
  DATA FIELDS:
    assessments: Array       ← List of templates (WI RN 10 Day, C-SSRS)
    selectedAssessment       ← Which one user selected
    form: Object             ← All form field values (Q1, Q2, ... Q60)
    member: Object           ← Member info (name, DOB, etc)
  
  METHODS:
    onValidate(): void       ← User clicks "Validate" button
      - Build request { submission, template }
      - Call ValidationService
      - Get response
      - Show results modal
    
    onAcceptFix(): void      ← User accepts auto-fix
      - Apply corrected value
      - Move to next issue
    
    onSaveSubmission(): void ← User saves corrected assessment
      - Send corrected data to database
      - Show success message

Why this structure?
  - Reactive data binding (form changes → UI updates instantly)
  - Clean separation (UI logic vs business logic)
  - Testable (each method can be unit tested)

Key insight:
  Component = "glue" between user and backend
  When user clicks → Call service → Get result → Update UI
```

---

### `frontend/src/app/app.component.html` - UI Template
```
Purpose: What user SEES. HTML + Angular directives.

Sections:
  1. Assessment Selector
     <select [(ngModel)]="selectedAssessment">
       WI RN 10 Day Assessment
       C-SSRS Suicide Risk Screener
     </select>
  
  2. Member Info Display
     Name: {{ member.name }}
     DOB: {{ member.dob }}
     Medicaid ID: {{ member.medicaidId }}
  
  3. Assessment Form (Dynamic)
     <div *ngFor="let question of questions">
       <label>{{ question.name }}</label>
       <input *ngIf="question.type=='text'" [(ngModel)]="form[question.id]" />
       <input *ngIf="question.type=='date'" [(ngModel)]="form[question.id]" type="date" />
       <select *ngIf="question.type=='button'" [(ngModel)]="form[question.id]">
         <option *ngFor="let opt of question.options">{{ opt }}</option>
       </select>
     </div>
  
  4. Buttons
     <button (click)="onValidate()">Validate</button>
     <button (click)="onSaveSubmission()">Save</button>
  
  5. Loading Spinner (during API call)
     <div *ngIf="isValidating">Processing...</div>
  
  6. Results Modal (after validation)
     <validation-modal [response]="validationResponse">
     </validation-modal>

Why this structure?
  - Template-driven forms (questions generated from JSON)
  - Two-way binding (ngModel) (form ↔ component)
  - Conditional rendering (*ngIf) (show/hide based on state)
  - Loops (*ngFor) (repeat for each question)

Key insight:
  HTML file defines WHAT to show
  .ts file defines WHEN and HOW
```

---

### `frontend/src/app/services/validation.service.ts` - Backend Communication
```
Purpose: Bridge between Angular frontend and Python backend.

What it does:
  METHOD: validateAssessment(request: ValidationRequest)
    1. Make HTTP POST request
    2. Send to: http://localhost:5000/api/validate
    3. Send data: { submission, template }
    4. Wait for response
    5. Handle errors (retry once)
    6. Return result to component
  
  EXAMPLE:
    this.validationService.validateAssessment(request).subscribe(
      (response) => {
        // Success! Process response
        this.validationResponse = response;
      },
      (error) => {
        // Error! Show error message
        this.validationError = error.message;
      }
    );

Why this structure?
  - Centralized backend calls (change one place)
  - Error handling built-in
  - Retry logic (if network fails, try again)
  - Observable pattern (async/await alternative)

Key insight:
  This is the ONLY place that talks to backend
  Components call this service, not backend directly
  Service handles all HTTP details
```

---

### `frontend/src/app/models/validation.models.ts` - TypeScript Interfaces
```
Purpose: Type definitions. Ensures data is correct format.

What it defines:
  interface ValidationRequest {
    submission: Submission;
    template: Template;
  }
  
  interface Submission {
    MemberId: string;
    StateID: string;
    pages: Page[];
  }
  
  interface ValidationResponse {
    status: "pass" | "review_needed" | "error";
    totalIssues: number;
    autoFixedCount: number;
    issues: ValidationIssue[];
  }
  
  interface ValidationIssue {
    questionId: string;
    errorType: string;
    originalValue: string;
    correctedValue: string;
    autoFixed: boolean;
  }

Why this structure?
  - TypeScript enforces types (catches errors at compile time)
  - IDE autocomplete (type `.response.` and see suggestions)
  - Clear contract (what data backend returns)
  - Self-documenting (read interface = understand data)

Key insight:
  Without types:
    response.totaleIssues  ← Typo! Won't catch until runtime
  
  With types:
    response.totalIssues   ← IDE will autocomplete/correct
```

---

### `frontend/src/app/components/validation-modal/` - Results Display
```
Purpose: Modal popup showing validation results.

Files:
  validation-modal.component.ts     - Logic
  validation-modal.component.html   - Display
  validation-modal.component.scss   - Styling

What it shows:
  ┌─────────────────────────────────┐
  │ VALIDATION RESULTS              │
  ├─────────────────────────────────┤
  │ Status: ✅ Review Needed        │
  │ Total Issues: 4                 │
  │ Auto-Fixed: ✅ 3                │
  │ Needs Review: ⚠️ 1              │
  │                                 │
  │ Issues:                         │
  │  ✅ Q2: Date format corrected   │
  │  ✅ Q44: Whitespace removed     │
  │  ⚠️ Q50: AI suggestion          │
  │                                 │
  │ [Accept All] [Review] [Reject]  │
  └─────────────────────────────────┘

Why separate component?
  - Reusable (show results anywhere)
  - Encapsulated (has its own logic)
  - Testable (test modal independently)
```

---

### `frontend/src/assets/` - Template Files
```
Purpose: JSON files defining assessment templates.

Files:
  template.json         - WI RN 10 Day Assessment rules
  cssrs_template.json   - C-SSRS Suicide Risk Screener rules

Contents example:
  {
    "id": "wi-rn-10day",
    "name": "WI RN 10 Day Assessment",
    "pages": [
      {
        "id": "page1",
        "name": "Health Status",
        "questions": [
          {
            "id": "Q1",
            "name": "Mobility Status",
            "type": "button",
            "required": true,
            "options": ["Independent", "Requires Assistance", "Dependent"]
          },
          {
            "id": "Q2",
            "name": "Assessment Date",
            "type": "date",
            "required": true,
            "validationRules": {
              "format": "YYYY-MM-DD"
            }
          }
        ]
      }
    ]
  }

Why this file?
  - Define rules once, use everywhere
  - Templates are data (not hardcoded)
  - Easy to add new assessments (new JSON file)
  - Backend reads same templates (no duplication)
```

---

## 📊 CONFIG FILES

### `backend/requirements.txt`
```
All Python packages needed.
To install: pip install -r requirements.txt
```

### `frontend/package.json`
```
All Node.js packages needed.
To install: npm install
To run: npm start
```

### `frontend/angular.json`
```
Angular build configuration.
- Build output folder
- Development server port
- Production settings
```

---

## 🔄 DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────┐
│ CARE MANAGER FILLS FORM IN BROWSER                     │
│ Q1: "Home", Q2: "01/15/2024", Q44: " 95 "              │
└──────────────────┬──────────────────────────────────────┘
                   │ Click "Validate"
                   ▼
        ┌──────────────────────┐
        │ app.component.ts     │
        │ Build request:       │
        │  {submission, ...}   │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │ validation.service.ts    │
        │ HTTP POST to backend     │
        │ Wait for response        │
        └──────────┬───────────────┘
                   │
                   │ Network
                   ▼
        ┌─────────────────────────────────────────┐
        │ backend/app.py                          │
        │ Receive request                         │
        └────────────┬────────────────────────────┘
                     │
                     ▼
        ┌─────────────────────────────────────────┐
        │ Agent 1: intake_agent.py                │
        │ Parse raw data → structured format     │
        │ Output: IntakeContext                  │
        └────────────┬────────────────────────────┘
                     │
                     ▼
        ┌─────────────────────────────────────────┐
        │ Agent 2: classifier_agent.py            │
        │ Check error type                        │
        │ Output: error_type + escalate flag     │
        └────────────┬────────────────────────────┘
                     │
                     ▼
        ┌─────────────────────────────────────────┐
        │ Agent 3: format_validator.py            │
        │ Validate all fields (8 checks)         │
        │ Output: List of issues found            │
        └────────────┬────────────────────────────┘
                     │
                     ▼
        ┌─────────────────────────────────────────┐
        │ Agent 4: correction_agent.py            │
        │ Tier 1: Auto-fix whitespace, dates     │
        │ Tier 2: AI suggestions (GPT-4o)         │
        │ Output: corrected_answers               │
        └────────────┬────────────────────────────┘
                     │
                     ▼
        ┌─────────────────────────────────────────┐
        │ Agent 5: report_agent.py                │
        │ Assemble all results                    │
        │ Output: Final JSON response             │
        └────────────┬────────────────────────────┘
                     │
                     │ JSON Response
                     ▼
        ┌──────────────────────────┐
        │ validation.service.ts    │
        │ Return response          │
        └────────────┬─────────────┘
                     │
                     ▼
        ┌──────────────────────┐
        │ app.component.ts     │
        │ Update UI state      │
        └────────────┬─────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ MODAL SHOWS RESULTS TO CARE MANAGER                   │
│  ✅ Date corrected: 01/15/2024 → 2024-01-15          │
│  ✅ Whitespace removed: " 95 " → "95"                │
│  ⚠️ AI suggestion for Q50 (review)                    │
└─────────────────────────────────────────────────────────┘
                     │
                     ▼ Care Manager Accepts
        ┌──────────────────────┐
        │ app.component.ts     │
        │ User clicks "Save"   │
        └────────────┬─────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │ Save corrected           │
        │ submission to database   │
        │ (or send to next system) │
        └──────────────────────────┘
```

---

## 📋 QUICK FILE REFERENCE

| File | Type | Purpose | Language |
|------|------|---------|----------|
| `app.py` | Backend | Main server orchestration | Python |
| `intake_agent.py` | Agent 1 | Parse & structure data | Python |
| `classifier_agent.py` | Agent 2 | Classify error type | Python |
| `format_validator.py` | Agent 3 | Validate all fields | Python |
| `correction_agent.py` | Agent 4 | Auto-fix + AI suggestions | Python |
| `report_agent.py` | Agent 5 | Build final response | Python |
| `ai_service.py` | Service | AI API integration | Python |
| `app.component.ts` | Frontend | Main component logic | TypeScript |
| `app.component.html` | Frontend | UI template | HTML |
| `validation.service.ts` | Frontend | Backend communication | TypeScript |
| `validation.models.ts` | Frontend | Type definitions | TypeScript |
| `template.json` | Config | Assessment template | JSON |

---

**Created:** August 16, 2026  
**For:** Complete understanding of codebase structure
