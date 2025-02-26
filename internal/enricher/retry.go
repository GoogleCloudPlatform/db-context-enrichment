/*
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package enricher

import (
	"context"
	"log"
	"math"
	"time"
)

// RetryOptions configures the retry behavior
type RetryOptions struct {
	MaxAttempts       int           // Maximum number of retry attempts
	InitialBackoff    time.Duration // Initial backoff duration
	MaxBackoff        time.Duration // Maximum backoff duration
	BackoffMultiplier float64       // Multiplier for exponential backoff
}

// DefaultRetryOptions provides sensible default retry settings
var DefaultRetryOptions = RetryOptions{
	MaxAttempts:       3,
	InitialBackoff:    100 * time.Millisecond,
	MaxBackoff:        2 * time.Second,
	BackoffMultiplier: 2.0,
}

// isRetryableError determines if an error should trigger a retry
func isRetryableError(err error) bool {
	switch err.(type) {
	case *ErrDatabaseConnection, *ErrTimeout, *ErrQueryExecution:
		return true
	case *ErrInvalidInput, *ErrCancelled:
		return false
	default:
		return false
	}
}

// withRetry executes the given operation with retry logic
func withRetry[T any](ctx context.Context, opts RetryOptions, op func(context.Context) (T, error)) (T, error) {
	var lastErr error
	var result T

	for attempt := 0; attempt < opts.MaxAttempts; attempt++ {
		select {
		case <-ctx.Done():
			if lastErr == nil {
				lastErr = &ErrCancelled{Msg: "operation cancelled by context", Err: ctx.Err()}
			}
			return result, lastErr
		default:
			// Calculate backoff duration
			backoff := opts.InitialBackoff * time.Duration(math.Pow(opts.BackoffMultiplier, float64(attempt)))
			if backoff > opts.MaxBackoff {
				backoff = opts.MaxBackoff
			}

			// Execute operation
			result, lastErr = op(ctx)
			if lastErr == nil {
				return result, nil
			}

			// Check if error is retryable
			if !isRetryableError(lastErr) {
				return result, lastErr
			}
			log.Printf("WARN: Operation failed on attempt %d with error: %v. Retrying in %v...", attempt+1, lastErr, backoff)
			// Wait before next attempt
			timer := time.NewTimer(backoff)
			select {
			case <-ctx.Done():
				timer.Stop()
				return result, &ErrCancelled{Msg: "operation cancelled during backoff", Err: ctx.Err()}
			case <-timer.C:
				continue
			}
		}
	}

	return result, lastErr
}
