// ============================================================
// Validation Models - TypeScript Interfaces
// ============================================================
// These interfaces match EXACTLY the JSON structure that
// our Python backend sends and receives.
// Field names must match backend schema precisely.
// ============================================================

// ── Submission Payload (sent TO our validation API) ────────
// Matches real mCare CCAAssessmentRequestBody structure

export interface AnswerValue {
  value: string;
}

export interface SubmissionQuestion {
  id    : string;
  answer: AnswerValue;
}

export interface SubmissionPage {
  id       : string;
  questions: SubmissionQuestion[];
}

export interface Submission {
  MemberId     : string;
  StateID      : string;
  templateGuid : string;
  version      : number;
  source       : string;
  score        : string;
  completedDate: string;
  caseId       : string;
  Registrar    : string;
  pages        : SubmissionPage[];
}

// ── Validation Request (what Angular sends to our API) ─────
export interface ValidationRequest {
  submission: Submission;
  template  : any;  // Full template JSON from mCare
}

// ── Validation Issue (returned by our API) ─────────────────
export interface ValidationIssue {
  questionId    : string;
  questionName  : string;
  errorType     : 'UserError' | 'TemplateIssue' | 'SystemIssue';
  severity      : 'High' | 'Medium' | 'Low';
  description   : string;
  originalValue : string;
  correctedValue: string | null;
  autoFixed     : boolean;
  suggestion    : string | null;
}

// ── Escalation Info ────────────────────────────────────────
export interface EscalationInfo {
  type     : string;
  routedTo : string;
  details  : string;
}

// ── Validation Response (what our API returns) ─────────────
export interface ValidationResponse {
  status            : 'valid' | 'auto_corrected' | 'needs_review' | 'escalated';
  summary           : string;
  totalIssues       : number;
  autoFixedCount    : number;
  needsReviewCount  : number;
  issues            : ValidationIssue[];
  correctedSubmission: Submission | null;
  escalation        : EscalationInfo | null;
  validatedAt       : string;
  templateName      : string;
  memberId          : string;
}