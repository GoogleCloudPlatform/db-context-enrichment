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
	"errors"
	"fmt"
)

// ErrDatabaseConnection represents errors that occur during database connection attempts
type ErrDatabaseConnection struct {
	Msg string
	Err error
}

// ErrQueryExecution represents errors that occur during query execution
type ErrQueryExecution struct {
	Msg string
	Err error
}

// ErrInvalidInput represents errors related to invalid input parameters
type ErrInvalidInput struct {
	Msg string
	Err error
}

// ErrTimeout represents timeout errors during operations
type ErrTimeout struct {
	Msg string
	Err error
}

// ErrCancelled represents errors when an operation is cancelled
type ErrCancelled struct {
	Msg string
	Err error
}

func (e *ErrDatabaseConnection) Error() string {
	return fmt.Sprintf("database connection error: %s: %w", e.Msg, e.Err)
}

func (e *ErrDatabaseConnection) Unwrap() error {
	return errors.Unwrap(e.Err)
}

func (e *ErrQueryExecution) Error() string {
	return fmt.Sprintf("query execution error: %s: %w", e.Msg, e.Err)
}

func (e *ErrQueryExecution) Unwrap() error {
	return errors.Unwrap(e.Err)
}

func (e *ErrInvalidInput) Error() string {
	return fmt.Sprintf("invalid input error: %s: %w", e.Msg, e.Err)
}

func (e *ErrInvalidInput) Unwrap() error {
	return errors.Unwrap(e.Err)
}

func (e *ErrTimeout) Error() string {
	return fmt.Sprintf("timeout error: %s: %w", e.Msg, e.Err)
}

func (e *ErrTimeout) Unwrap() error {
	return errors.Unwrap(e.Err)
}

func (e *ErrCancelled) Error() string {
	return fmt.Sprintf("operation cancelled: %s: %w", e.Msg, e.Err)
}

func (e *ErrCancelled) Unwrap() error {
	return errors.Unwrap(e.Err)
}
