// ============================================================
// Validation Service
// ============================================================
// PURPOSE:
//   Handles all HTTP communication between Angular frontend
//   and the Python Flask validation backend.
//
// ANALOGY FOR PPT:
//   Think of this as the "messenger" — Angular fills the
//   assessment form, service sends it to Flask backend,
//   gets the validation result back, and returns it to
//   the component for display.
//
// CALLED BY:
//   AppComponent / PerformAssessmentComponent
// ============================================================

import { Injectable }                    from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError }        from 'rxjs';
import { catchError, retry }             from 'rxjs/operators';
import { ValidationRequest, ValidationResponse, Submission } from '../models/validation.models';

@Injectable({
  providedIn: 'root'
})
export class ValidationService {

  // Backend URL — Flask running on port 5000
  // Relative path '/api' works when served from Flask, absolute fallback for dev
  private apiUrl = '/api';

  constructor(private http: HttpClient) {}

  // ── Main Method: Validate Assessment (Read-Only) ────────
  // Sends submission + template to Python backend
  // Returns Observable<ValidationResponse>
  validateAssessment(
    request: ValidationRequest
  ): Observable<ValidationResponse> {
    return this.http
      .post<ValidationResponse>(
        `${this.apiUrl}/validate`,
        request
      )
      .pipe(
        retry(1),              // Retry once on transient network error
        catchError(this.handleError)
      );
  }

  // ── Submit Assessment (Validate + Transmit with Retry) ──
  // Calls the new /api/submit endpoint for end-to-end CCA transport
  submitAssessment(
    request: ValidationRequest
  ): Observable<ValidationResponse> {
    return this.http
      .post<ValidationResponse>(
        `${this.apiUrl}/submit`,
        request
      )
      .pipe(
        catchError(this.handleError)
      );
  }

  // ── Load Production Error Test Fixture ──────────────────
  // Fetches the sample payload containing all 5 production errors
  getProdErrorFixture(): Observable<Submission> {
    return this.http
      .get<Submission>(`${this.apiUrl}/sample-data/prod-errors`)
      .pipe(
        catchError(this.handleError)
      );
  }

  // ── Load Baseline Submission Fixture ────────────────────
  getBaseSubmission(): Observable<Submission> {
    return this.http
      .get<Submission>(`${this.apiUrl}/sample-data/submission`)
      .pipe(
        catchError(this.handleError)
      );
  }

  // ── Health Check ────────────────────────────────────────
  checkHealth(): Observable<any> {
    return this.http
      .get(`${this.apiUrl}/health`)
      .pipe(catchError(this.handleError));
  }

  // ── Error Handler ───────────────────────────────────────
  private handleError(error: HttpErrorResponse): Observable<never> {
    let errorMessage = 'An unknown error occurred';

    if (error.status === 0) {
      // Network error — backend not reachable
      errorMessage =
        'Unable to connect to Validation Agent. ' +
        'Please ensure the backend service is running.';
    } else if (error.status === 400) {
      errorMessage =
        error.error?.message || 'Invalid request format.';
    } else if (error.status === 422) {
      errorMessage =
        error.error?.message || 'Assessment validation escalated or failed business rules.';
    } else if (error.status === 500) {
      errorMessage =
        'Validation Agent server error. Please try again.';
    } else {
      errorMessage = `Error ${error.status}: ${error.message}`;
    }

    return throwError(() => new Error(errorMessage));
  }
}