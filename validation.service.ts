// ============================================================
// Validation Service
// ============================================================
// PURPOSE:
//   Handles all HTTP communication between Angular frontend
//   and our Python Flask validation backend.
//
// ANALOGY FOR PPT:
//   Think of this as the "messenger" — Angular fills the
//   assessment form, service sends it to Flask backend,
//   gets the validation result back, and returns it to
//   the component for display.
//
// CALLED BY:
//   AppComponent — when Care Manager clicks "Validate"
// ============================================================

import { Injectable }                    from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError }        from 'rxjs';
import { catchError, retry }             from 'rxjs/operators';
import { ValidationRequest, ValidationResponse } from '../models/validation.models';

@Injectable({
  providedIn: 'root'
})
export class ValidationService {

  // Backend URL — Flask running on port 8080
  // In production this would be the Azure/IIS URL
  private apiUrl = 'http://localhost:8080/api';

  constructor(private http: HttpClient) {}

  // ── Main Method: Validate Assessment ───────────────────
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
        retry(1),              // Retry once on network error
        catchError(this.handleError)
      );
  }

  // ── Health Check ────────────────────────────────────────
  checkHealth(): Observable<any> {
    return this.http
      .get(`${this.apiUrl}/health`)
      .pipe(catchError(this.handleError));
  }

  // ── Error Handler ────────────────────────────────────────
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
    } else if (error.status === 500) {
      errorMessage =
        'Validation Agent server error. Please try again.';
    } else {
      errorMessage = `Error ${error.status}: ${error.message}`;
    }

    return throwError(() => new Error(errorMessage));
  }
}