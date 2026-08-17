// ============================================================
// Validation Modal Component
// ============================================================
// PURPOSE:
//   Displays the validation results in a modal dialog.
//   Shows all issues found, auto-corrections made,
//   AI suggestions, escalation warnings, pruned questions,
//   DB timeout risk advisories, and CCA direct transport results.
//
// RECEIVES:
//   - response: the full result from backend
//   - closeModal: callback to close modal
//   - applyCorrections: callback to apply auto-fixes
//   - submitAnyway: callback to transmit directly to CCA
// ============================================================

import { Component, Input, Output, EventEmitter } from '@angular/core';
import { ValidationResponse, ValidationIssue } from '../../models/validation.models';

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

  // ── Issue & Classification Getters ──────────────────────

  get autoFixedIssues(): ValidationIssue[] {
    return this.response?.issues?.filter(
      i => i.autoFixed === true && !(i as any).pruned
    ) || [];
  }

  get needsReviewIssues(): ValidationIssue[] {
    return this.response?.issues?.filter(
      i => i.autoFixed === false && !(i as any).pruned
    ) || [];
  }

  get statusIcon(): string {
    const icons: Record<string, string> = {
      valid          : 'bi-check-circle-fill',
      auto_corrected : 'bi-magic',
      needs_review   : 'bi-exclamation-triangle-fill',
      escalated      : 'bi-x-circle-fill',
      error          : 'bi-exclamation-octagon-fill'
    };
    return icons[this.response?.status] || 'bi-info-circle';
  }

  get statusLabel(): string {
    const labels: Record<string, string> = {
      valid          : 'All Checks Passed',
      auto_corrected : 'Auto-Corrected',
      needs_review   : 'Needs Review',
      escalated      : 'Escalated to Support',
      error          : 'Validation Error'
    };
    return labels[this.response?.status] || 'Unknown';
  }

  get headerClass(): string {
    return `modal-header-${this.response?.status || 'needs_review'}`;
  }

  getScoreColor(score: number): string {
    if (score >= 8) return '#28a745';
    if (score >= 6) return '#ffc107';
    return '#dc3545';
  }

  // ── CCA Production Error & Transport Helpers ─────────────

  get hasPrunedQuestions(): boolean {
    return (this.response?.prunedQuestions?.length ?? 0) > 0;
  }

  get isHighTimeoutRisk(): boolean {
    return this.response?.timeoutRisk?.level === 'high';
  }

  get isTransportSuccess(): boolean {
    return this.response?.transport?.success === true;
  }

  get isTransportFailed(): boolean {
    return this.response?.transport !== undefined && !this.response.transport.success;
  }

  // ── Extract AI suggestion text ──────────────────────────

  getAiSuggestion(issue: ValidationIssue): string {
    if (!issue.suggestion) return '';
    return issue.suggestion.replace(/^AI Suggestion:\s*/i, '');
  }

  // ── Check if suggestion is AI generated ─────────────────

  isAiSuggestion(issue: ValidationIssue): boolean {
    return issue.suggestion?.startsWith('AI Suggestion:') || false;
  }

  // ── Event Handlers ──────────────────────────────────────

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