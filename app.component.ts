// ============================================================
// App Component - Main Assessment Form
// ============================================================
// PURPOSE:
//   The main screen Care Manager sees. Mimics the mCareNG
//   assessment form layout with:
//   - Member information header
//   - Assessment questions (textarea, buttongroup, text)
//   - Validate button → calls our Python backend
//   - Shows validation modal with results
//   - Apply corrections → updates form fields
//
// ANALOGY FOR PPT:
//   This is the "front desk" of the application.
//   Care Manager fills the form here, clicks Validate,
//   sees results in modal, applies corrections, submits.
// ============================================================

import { Component, OnInit } from '@angular/core';
import { ValidationService } from './services/validation.service';
import {
  ValidationRequest,
  ValidationResponse,
  Submission
} from './models/validation.models';

@Component({
  selector   : 'app-root',
  templateUrl: './app.component.html',
  styleUrls  : ['./app.component.scss']
})
export class AppComponent implements OnInit {

  // ── UI State ────────────────────────────────────────────
  isValidating    = false;
  showModal       = false;
  showToast       = false;
  toastMessage    = '';
  validationError = '';
  isValidated     = false;

  // ── Validation Result ────────────────────────────────────
  validationResponse: ValidationResponse | null = null;

  // ── Member Info (pre-filled like mCareNG) ───────────────
  member = {
    name      : 'David Warner',
    medicaidId: '8327321234',
    dob       : '04/19/1989',
    state     : 'WI',
    gender    : 'M',
    caseId    : 'CASE-2026-001'
  };

  // ── Assessment Form Fields ───────────────────────────────
  // These represent the answers Care Manager fills in
  form = {
    // Page 2 - General Info
    assessmentDate : '08/08/2026',

    // Page 3 - Initial Review
    Q8  : '',   // Imminent dangers
    Q10 : '',   // Medication assistance
    Q12 : '',   // Support system change
    Q14 : '',   // Cognitive impairment
    Q16 : '',   // Recent transitions
    Q18 : '',   // Sufficient supports
    Q20 : '',   // Currently hospitalized
    Q21 : '',   // Discharge needs (conditional on Q20=Yes)

    // Page 4 - Medication Review
    Q23 : '',   // Reconciled medication list
    Q24 : '',   // Can set up own medications
    Q26 : '',   // Can administer own medications
    Q28 : '',   // Can monitor own medications
    Q30 : '',   // Medication interventions

    // Page 5 - Vulnerable/High Risk
    Q31 : '',   // Single caregiver
    Q33 : '',   // Two or more caregivers
    Q37 : '',   // Dependent on caregiver
    Q39 : '',   // Nonverbal/limited communication
    Q63 : '',   // Unable to make decisions
    Q65 : '',   // Clinically complex needs
    Q67 : '',   // Medically frail

    // Page 6 - VHRM
    Q44 : '',   // Total Points (auto-calculated)

    // Page 7 - Caregiver Verification
    Q45 : '',   // Skills verification completed
    Q47 : '',   // Concerns during skills verification
    Q48 : '',   // Skills verification concerns text
    Q49 : '',   // Strain assessment completed
    Q51 : '',   // Concerns during strain assessment
    Q52 : '',   // Strain assessment concerns text

    // Page 8 - Additional
    Q55 : ''    // Additional comments
  };

  // ── Full Template JSON ───────────────────────────────────
  // In production this comes from mCare database
  // For POC we embed the WI RN 10 Day template
  private template: any = null;

  constructor(private validationService: ValidationService) {}

  ngOnInit(): void {
    this.loadTemplate();
    this.loadDemoScenario();
  }

  // ── Load Template ────────────────────────────────────────
  // In production: fetched from mCare API
  // For POC: loaded from assets folder
  private loadTemplate(): void {
    // Template will be loaded from assets
    // We'll set it up as a fetch from assets/template.json
    fetch('assets/template.json')
      .then(r => r.json())
      .then(t => {
        this.template = t;
        console.log('Template loaded:', t.name);
      })
      .catch(() => {
        console.warn('Template not found in assets, using inline');
        this.template = { id: 1893, name: 'WI RN 10 Day Assessment',
                          pages: [], rules: [] };
      });
  }

  // ── Load Demo Scenario ───────────────────────────────────
  // Pre-fills form with intentional errors for demo
  private loadDemoScenario(): void {
    this.form.Q8   = 'Yes';
    this.form.Q10  = 'No';
    this.form.Q12  = 'Yes';
    this.form.Q14  = 'No';
    this.form.Q16  = 'Yes';
    this.form.Q18  = 'Yes';
    this.form.Q20  = 'Yes';
    this.form.Q21  = '';      // Intentionally empty (should trigger)
    this.form.Q23  = 'Yes';
    this.form.Q24  = 'No';
    this.form.Q26  = 'N/A';
    this.form.Q28  = 'Yes';
    this.form.Q31  = 'Yes';
    this.form.Q33  = 'No';
    this.form.Q37  = 'Yes';
    this.form.Q39  = 'No';
    this.form.Q63  = 'Yes';
    this.form.Q65  = 'Yes';
    this.form.Q67  = 'No';
    this.form.Q44  = '  3  '; // Intentional whitespace error
    this.form.Q45  = 'Yes';
    this.form.Q47  = 'Yes';
    this.form.Q48  = '';      // Intentionally empty
    this.form.Q49  = 'Yes';
    this.form.Q51  = 'Yes';
    this.form.Q52  = '';      // Intentionally empty
  }

  // ── Build Submission Payload ─────────────────────────────
  // Constructs the real mCare CCAAssessmentRequestBody
  // from the form fields
  private buildSubmission(): Submission {
    return {
      MemberId     : this.member.medicaidId,
      StateID      : this.member.state,
      templateGuid : 'wi-rn-10day-v1',
      version      : 1,
      source       : 'mCare-Web-POC',
      score        : '',
      completedDate: new Date().toISOString(),
      caseId       : this.member.caseId,
      Registrar    : 'satyaadarsh.bikkina',
      pages        : [
        {
          id: '2',
          questions: [
            { id: 'Q1', answer: { value: 'David' } },
            { id: 'Q2', answer: { value: 'Warner' } },
            { id: 'Q4', answer: { value: this.member.dob } },
            { id: 'Q3', answer: { value: this.member.medicaidId } },
            { id: 'Q5', answer: { value: this.form.assessmentDate } }
          ]
        },
        {
          id: '3',
          questions: [
            { id: 'Q8',  answer: { value: this.form.Q8  } },
            { id: 'Q9',  answer: { value: '' } },
            { id: 'Q10', answer: { value: this.form.Q10 } },
            { id: 'Q11', answer: { value: '' } },
            { id: 'Q12', answer: { value: this.form.Q12 } },
            { id: 'Q13', answer: { value: '' } },
            { id: 'Q14', answer: { value: this.form.Q14 } },
            { id: 'Q15', answer: { value: '' } },
            { id: 'Q16', answer: { value: this.form.Q16 } },
            { id: 'Q17', answer: { value: '' } },
            { id: 'Q18', answer: { value: this.form.Q18 } },
            { id: 'Q19', answer: { value: '' } },
            { id: 'Q20', answer: { value: this.form.Q20 } },
            { id: 'Q21', answer: { value: this.form.Q21 } },
            { id: 'Q22', answer: { value: '' } }
          ]
        },
        {
          id: '4',
          questions: [
            { id: 'Q23', answer: { value: this.form.Q23 } },
            { id: 'Q24', answer: { value: this.form.Q24 } },
            { id: 'Q25', answer: { value: '' } },
            { id: 'Q26', answer: { value: this.form.Q26 } },
            { id: 'Q27', answer: { value: '' } },
            { id: 'Q28', answer: { value: this.form.Q28 } },
            { id: 'Q29', answer: { value: '' } },
            { id: 'Q30', answer: { value: this.form.Q30 } }
          ]
        },
        {
          id: '5',
          questions: [
            { id: 'Q31', answer: { value: this.form.Q31 } },
            { id: 'Q32', answer: { value: '' } },
            { id: 'Q33', answer: { value: this.form.Q33 } },
            { id: 'Q37', answer: { value: this.form.Q37 } },
            { id: 'Q38', answer: { value: '' } },
            { id: 'Q39', answer: { value: this.form.Q39 } },
            { id: 'Q63', answer: { value: this.form.Q63 } },
            { id: 'Q64', answer: { value: '' } },
            { id: 'Q65', answer: { value: this.form.Q65 } },
            { id: 'Q66', answer: { value: '' } },
            { id: 'Q67', answer: { value: this.form.Q67 } },
            { id: 'Q68', answer: { value: '' } }
          ]
        },
        {
          id: '6',
          questions: [
            { id: 'Q69', answer: { value: 'Yes' } },
            { id: 'Q44', answer: { value: this.form.Q44 } }
          ]
        },
        {
          id: '7',
          questions: [
            { id: 'Q45', answer: { value: this.form.Q45 } },
            { id: 'Q46', answer: { value: '08/08/2026' } },
            { id: 'Q47', answer: { value: this.form.Q47 } },
            { id: 'Q48', answer: { value: this.form.Q48 } },
            { id: 'Q49', answer: { value: this.form.Q49 } },
            { id: 'Q50', answer: { value: '08/08/2026' } },
            { id: 'Q51', answer: { value: this.form.Q51 } },
            { id: 'Q52', answer: { value: this.form.Q52 } },
            { id: 'Q53', answer: { value: 'Yes' } },
            { id: 'Q54', answer: { value: '' } }
          ]
        },
        {
          id: '8',
          questions: [
            { id: 'Q55', answer: { value: this.form.Q55 } }
          ]
        }
      ]
    };
  }

  // ── Validate Button Click ────────────────────────────────
  onValidate(): void {
    this.isValidating    = true;
    this.validationError = '';
    this.isValidated     = false;

    const request: ValidationRequest = {
      submission: this.buildSubmission(),
      template  : this.template
    };

    this.validationService
      .validateAssessment(request)
      .subscribe({
        next : (response) => {
          this.validationResponse = response;
          this.isValidating       = false;
          this.showModal          = true;
        },
        error: (err) => {
          this.isValidating    = false;
          this.validationError = err.message;
        }
      });
  }

  // ── Apply Corrections ────────────────────────────────────
  // Takes corrected values from backend response
  // and updates form fields
  onApplyCorrections(): void {
    if (!this.validationResponse?.correctedSubmission) return;

    const corrected = this.validationResponse.correctedSubmission;
    let   fixCount  = 0;

    // Loop through corrected pages and questions
    corrected.pages.forEach(page => {
      page.questions.forEach(q => {
        const qId    = q.id as keyof typeof this.form;
        const newVal = q.answer.value;

        // Only update if value changed
        if (qId in this.form &&
            (this.form as any)[qId] !== newVal &&
            newVal !== '') {
          (this.form as any)[qId] = newVal;
          fixCount++;
        }
      });
    });

    this.showModal   = false;
    this.isValidated = true;

    // Show toast notification
    this.showToastMessage(
      `${fixCount} correction(s) applied. Please review and submit.`
    );
  }

  // ── Close Modal ──────────────────────────────────────────
  onCloseModal(): void {
    this.showModal = false;
  }

  // ── Submit to CCA ────────────────────────────────────────
  onSubmitToCCA(): void {
    this.showToastMessage(
      'Assessment submitted to CCA successfully!'
    );
    this.showModal   = false;
    this.isValidated = false;
  }

  // ── Toast Helper ─────────────────────────────────────────
  showToastMessage(msg: string): void {
    this.toastMessage = msg;
    this.showToast    = true;
    setTimeout(() => { this.showToast = false; }, 4000);
  }

  // ── Button Group Helper ──────────────────────────────────
  setAnswer(field: string, value: string): void {
    (this.form as any)[field] = value;
    this.isValidated = false;
  }

  getButtonClass(field: string, value: string): string {
    const current = (this.form as any)[field];
    if (current !== value) return 'btn-option';
    if (value === 'Yes') return 'btn-option selected-yes';
    if (value === 'No')  return 'btn-option selected-no';
    if (value === 'N/A') return 'btn-option selected-na';
    return 'btn-option';
  }
}