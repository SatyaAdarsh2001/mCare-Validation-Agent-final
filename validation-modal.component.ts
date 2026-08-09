// ============================================================
// Validation Modal Component
// ============================================================
// PURPOSE:
//   Displays the validation results in a modal dialog.
//   Shows all issues found, auto-corrections made,
//   AI suggestions, and escalation warnings.
//
// RECEIVES:
//   - validationResponse: the full result from backend
//   - onClose: callback to close modal
//   - onApplyCorrections: callback to apply auto-fixes
// ============================================================

import { Component, Input, Output, EventEmitter } from '@angular/core';
import { ValidationResponse, ValidationIssue }    from '../../models/validation.models';

@Component({
  selector   : 'app-validation-modal',
  templateUrl: './validation-modal.component.html',
  styleUrls  : ['./validation-modal.component.scss']
})
export class ValidationModalComponent {

  @Input()  response          !: ValidationResponse;
  @Output() closeModal         = new EventEmitter<void>();
  @Output() applyCorrections   = new EventEmitter<void>();
  @Output() submitAnyway       = new EventEmitter<void>();

  // ── Getters for template use ────────────────────────────

  get autoFixedIssues(): ValidationIssue[] {
    return this.response?.issues?.filter(
      i => i.autoFixed === true
    ) || [];
  }

  get needsReviewIssues(): ValidationIssue[] {
    return this.response?.issues?.filter(
      i => i.autoFixed === false
    ) || [];
  }

  get statusIcon(): string {
    const icons: Record<string, string> = {
      valid          : 'bi-check-circle-fill',
      auto_corrected : 'bi-magic',
      needs_review   : 'bi-exclamation-triangle-fill',
      escalated      : 'bi-x-circle-fill'
    };
    return icons[this.response?.status] || 'bi-info-circle';
  }

  get statusLabel(): string {
    const labels: Record<string, string> = {
      valid          : 'All Checks Passed',
      auto_corrected : 'Auto-Corrected',
      needs_review   : 'Needs Review',
      escalated      : 'Escalated to Support'
    };
    return labels[this.response?.status] || 'Unknown';
  }

  get headerClass(): string {
    return `modal-header-${this.response?.status}`;
  }

  // ── Extract AI suggestion text ──────────────────────────
  getAiSuggestion(issue: ValidationIssue): string {
    if (!issue.suggestion) return '';
    return issue.suggestion.replace('AI Suggestion: ', '');
  }

  // ── Check if suggestion is AI generated ────────────────
  isAiSuggestion(issue: ValidationIssue): boolean {
    return issue.suggestion?.startsWith('AI Suggestion:') || false;
  }

  // ── Event handlers ──────────────────────────────────────
  onClose(): void {
    this.closeModal.emit();
  }

  onApplyCorrections(): void {
    this.applyCorrections.emit();
  }

  onSubmitAnyway(): void {
    this.submitAnyway.emit();
  }
}