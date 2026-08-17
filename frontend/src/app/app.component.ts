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

  // ── UI State ─────────────────────────────────────────────
  isValidating    = false;
  showModal       = false;
  showToast       = false;
  toastMessage    = '';
  validationError = '';
  isValidated     = false;

  validationResponse: ValidationResponse | null = null;

  // ── Assessment Switcher ───────────────────────────────────
  assessments = [
    {
      id          : 'wi-rn-10day',
      name        : 'WI RN 10 Day Assessment',
      templateFile: 'assets/template.json',
      memberId    : '9652320756',
      memberName  : 'SATYA ADARSH BIKKINA',
      dob         : '02/06/2001',
      gender      : 'M',
      state       : 'WI',
      caseId      : 'CASE-2026-001'
    },
    {
      id          : 'cssrs',
      name        : 'C-SSRS Suicide Risk Screener',
      templateFile: 'assets/cssrs_template.json',
      memberId    : '1234567890',
      memberName  : 'RAUNAK KUMAR',
      dob         : '06/22/1998',
      gender      : 'M',
      state       : 'OH',
      caseId      : 'CASE-2026-002'
    }
  ];

  selectedAssessment = this.assessments[0];

  // ── Member Info ───────────────────────────────────────────
  member = {
    name      : 'Satya Adarsh Bikkina',
    medicaidId: '9652320756',
    dob       : '02/06/2001',
    state     : 'WI',
    gender    : 'M',
    caseId    : 'CASE-2026-001'
  };

  // ── Form Fields (WI RN 10 Day) ────────────────────────────
  form: any = {
    assessmentDate: '08/08/2026',
    Q8: '', Q10: '', Q12: '', Q14: '',
    Q16: '', Q18: '', Q20: '', Q21: '',
    Q23: '', Q24: '', Q26: '', Q28: '', Q30: '',
    Q31: '', Q32: '', Q33: '',
    Q37: '', Q38: '', Q39: '',
    Q63: '', Q64: '', Q65: '', Q66: '', Q67: '', Q68: '',
    Q44: '',
    Q45: '', Q47: '', Q48: '',
    Q49: '', Q51: '', Q52: '',
    Q55: ''
  };

  // ── C-SSRS Form Fields ────────────────────────────────────
  cssrsForm: any = {
    Q1: '', Q2: '', Q3: '', Q4: '',
    Q5: '', Q6: '', Q7: '', Q8: ''
  };

  // ── Templates ─────────────────────────────────────────────
  private wiTemplate   : any = null;
  private cssrsTemplate: any = null;

  constructor(private validationService: ValidationService) {}

  ngOnInit(): void {
    this.loadWiTemplate();
    this.loadCssrsTemplate();
    this.loadDemoScenario();
    
    // Initialize member details from selected assessment
    this.member.medicaidId = this.selectedAssessment.memberId;
    this.member.dob        = this.selectedAssessment.dob;
    this.member.gender     = this.selectedAssessment.gender;
    this.member.state      = this.selectedAssessment.state;
    this.member.caseId     = this.selectedAssessment.caseId;
    this.member.name       = this.selectedAssessment.memberName
      .split(' ')
      .map((w: string) => w.charAt(0) + w.slice(1).toLowerCase())
      .join(' ');
  }

  private loadWiTemplate(): void {
    fetch('assets/template.json')
      .then(r => r.json())
      .then(t => { this.wiTemplate = t; })
      .catch(() => {
        this.wiTemplate = { id: 1893, name: 'WI RN 10 Day Assessment', pages: [], rules: [] };
      });
  }

  private loadCssrsTemplate(): void {
    fetch('assets/cssrs_template.json')
      .then(r => r.json())
      .then(t => { this.cssrsTemplate = t; })
      .catch(e => console.warn('C-SSRS template load failed', e));
  }

  private loadDemoScenario(): void {
    this.form.Q8  = 'Yes'; this.form.Q10 = 'No';
    this.form.Q12 = 'Yes'; this.form.Q14 = 'No';
    this.form.Q16 = 'Yes'; this.form.Q18 = 'Yes';
    this.form.Q20 = 'Yes'; this.form.Q21 = '';
    this.form.Q23 = 'Yes'; this.form.Q24 = 'No';
    this.form.Q26 = 'N/A'; this.form.Q28 = 'Yes';
    this.form.Q31 = 'Yes';
    this.form.Q32 = '';
    this.form.Q33 = 'No';

    this.form.Q37 = 'Yes';
    this.form.Q38 = '';
    this.form.Q39 = 'No';

    this.form.Q63 = 'Yes';
    this.form.Q64 = '';
    this.form.Q65 = 'Yes';
    this.form.Q66 = '';
    this.form.Q67 = 'No';
    this.form.Q68 = ''; this.form.Q44 = '  3  ';
    this.form.Q45 = 'Yes'; this.form.Q47 = 'Yes';
    this.form.Q48 = '';    this.form.Q49 = 'Yes';
    this.form.Q51 = 'Yes'; this.form.Q52 = '';

    // C-SSRS demo — intentional errors
    this.cssrsForm.Q1 = 'Yes';
    this.cssrsForm.Q2 = 'Yes';
    this.cssrsForm.Q3 = '';   // empty — conditional on Q2=Yes
    this.cssrsForm.Q4 = '';   // empty — conditional on Q2=Yes
    this.cssrsForm.Q5 = '';   // empty — conditional on Q2=Yes
    this.cssrsForm.Q6 = 'Yes';
    this.cssrsForm.Q7 = '';   // empty — conditional on Q6=Yes
  }

  // ── Assessment Switcher ───────────────────────────────────
  onAssessmentChange(assessmentId: string): void {
    this.selectedAssessment = this.assessments.find(
      a => a.id === assessmentId
    )!;
    this.isValidated        = false;
    this.validationResponse = null;
    this.validationError    = '';

    // Update ALL member info for selected assessment
    this.member.medicaidId = this.selectedAssessment.memberId;
    this.member.dob        = this.selectedAssessment.dob;
    this.member.gender     = this.selectedAssessment.gender;
    this.member.state      = this.selectedAssessment.state;
    this.member.caseId     = this.selectedAssessment.caseId;
    this.member.name       = this.selectedAssessment.memberName
      .split(' ')
      .map((w: string) => w.charAt(0) + w.slice(1).toLowerCase())
      .join(' ');
  }

  get isCssrs(): boolean {
    return this.selectedAssessment.id === 'cssrs';
  }

  get currentTemplate(): any {
    return this.isCssrs ? this.cssrsTemplate : this.wiTemplate;
  }

  // ── Build Submission ──────────────────────────────────────
  private buildSubmission(): Submission {
    if (this.isCssrs) {
      return this.buildCssrsSubmission();
    }
    return this.buildWiSubmission();
  }

  private buildWiSubmission(): Submission {
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
            { id: 'Q1', answer: { value: 'Satya' } },
            { id: 'Q2', answer: { value: 'Adarsh' } },
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
            { id: 'Q32', answer: { value: this.form.Q32 } },
            { id: 'Q33', answer: { value: this.form.Q33 } },
            { id: 'Q37', answer: { value: this.form.Q37 } },
            { id: 'Q38', answer: { value: this.form.Q38 } },
            { id: 'Q39', answer: { value: this.form.Q39 } },
            { id: 'Q63', answer: { value: this.form.Q63 } },
            { id: 'Q64', answer: { value: this.form.Q64 } },
            { id: 'Q65', answer: { value: this.form.Q65 } },
            { id: 'Q66', answer: { value: this.form.Q66 } },
            { id: 'Q67', answer: { value: this.form.Q67 } },
            { id: 'Q68', answer: { value: this.form.Q68 } }
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
            { id: 'Q55', answer: { value: this.form.Q55 } },
            // Intentional error triggers, always sent as part of the
            // normal payload so Validate/Submit exercise them for real
            // instead of via a separate demo-only button:
            //  - large text block -> DB Timeout risk (CCA error id=1000)
            //  - QID 263 -> invalid/unknown question id (CCA error id=7)
            ////{ id: 'Q900', answer: { value: 'Long narrative clinical observation '.repeat(150) } },
            //{ id: '263', answer: { value: 'Invalid QID 263 Value' } }
          ]
        }
      ]
    };
  }

  private buildCssrsSubmission(): Submission {
    return {
      MemberId     : this.member.medicaidId,
      StateID      : this.member.state,
      templateGuid : 'cssrs-v1',
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
            { id: 'Q1', answer: { value: this.cssrsForm.Q1 } },
            { id: 'Q2', answer: { value: this.cssrsForm.Q2 } },
            { id: 'Q3', answer: { value: this.cssrsForm.Q3 } },
            { id: 'Q4', answer: { value: this.cssrsForm.Q4 } },
            { id: 'Q5', answer: { value: this.cssrsForm.Q5 } },
            { id: 'Q6', answer: { value: this.cssrsForm.Q6 } },
            { id: 'Q7', answer: { value: this.cssrsForm.Q7 } }
          ]
        },
        {
          id: '3',
          questions: [
            { id: 'Q8', answer: { value: this.cssrsForm.Q8 } }
          ]
        }
      ]
    };
  }

  // ── Validate ──────────────────────────────────────────────
  onValidate(): void {
    this.isValidating    = true;
    this.validationError = '';
    this.isValidated     = false;

    const request: ValidationRequest = {
      submission: this.buildSubmission(),
      template  : this.currentTemplate
    };

    this.validationService.validateAssessment(request).subscribe({
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

  // ── Apply Corrections ─────────────────────────────────────
  onApplyCorrections(): void {
    if (!this.validationResponse?.correctedSubmission) return;
    const corrected = this.validationResponse.correctedSubmission;
    let fixCount = 0;
    corrected.pages.forEach(page => {
      page.questions.forEach(q => {
        const newVal = q.answer.value;
        const target = this.isCssrs ? this.cssrsForm : this.form;
        if (q.id in target && target[q.id] !== newVal && newVal !== '') {
          target[q.id] = newVal;
          fixCount++;
        }
      });
    });

    const needsReview = this.validationResponse.needsReviewCount || 0;

    // Only close the modal + mark validated when nothing is left
    // needing human review. Otherwise keep it open so the user can
    // actually see and act on the flagged items.
    if (needsReview > 0) {
      this.showToastMessage(
        `${fixCount} correction(s) applied. ${needsReview} item(s) still need your review below.`
      );
      return;
    }

    this.showModal   = false;
    this.isValidated = true;
    this.showToastMessage(`${fixCount} correction(s) applied. Please review and submit.`);
  }

  onCloseModal(): void { 
    this.showModal = false; 
  }

  onSubmitToCCA(): void {
    if (!this.validationResponse) return;

    const request: ValidationRequest = {
      submission: this.validationResponse.correctedSubmission || this.buildSubmission(),
      template  : this.currentTemplate
    };

    this.isValidating = true;
    this.validationService.submitAssessment(request).subscribe({
      next: (response) => {
        this.isValidating = false;
        this.showModal    = false;
        this.isValidated  = false;

        const transport = (response as any).transport;
        const risk = (response as any).timeoutRisk;
        const riskNote = risk?.level === 'high' ? ` High DBTimeout risk was detected — ${risk.recommendation}` : '';

        if (transport?.success) {
          this.showToastMessage(`Assessment submitted to CCA successfully!${riskNote}`);
        } else if (transport) {
          this.showToastMessage(
            `CCA submission failed after ${transport.attempts} attempt(s): ${transport.error_message || 'unknown error'}${riskNote}`
          );
        } else {
          this.showToastMessage('Submission blocked — validation issues must be resolved first.');
        }
      },
      error: (err) => {
        this.isValidating = false;
        this.showToastMessage(`Submit failed: ${err.message}`);
      }
    });
  }

  showToastMessage(msg: string): void {
    this.toastMessage = msg;
    this.showToast    = true;
    setTimeout(() => { this.showToast = false; }, 4000);
  }

  setAnswer(field: string, value: string, isCssrs = false): void {
    const target = isCssrs ? this.cssrsForm : this.form;
    if (target[field] === value) {
      target[field] = '';
    } else {
      target[field] = value;
    }
    this.isValidated = false;
  }

  getButtonClass(field: string, value: string, isCssrs = false): string {
    const current = isCssrs ? this.cssrsForm[field] : this.form[field];
    if (current !== value) return 'btn-option';
    if (value === 'Yes') return 'btn-option selected-yes';
    if (value === 'No')  return 'btn-option selected-no';
    if (value === 'N/A') return 'btn-option selected-na';
    return 'btn-option';
  }
}