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

// ColumnMetadata represents enrichment data for a column
type ColumnMetadata struct {
	Table         string   // Table name
	Column        string   // Column name
	DataType      string   // Column datatype
	ExampleValues []string // Sample of distinct values
	DistinctCount int64    // Total number of distinct values
	NullCount     int64    // Number of NULL values
	Description   string   // Description of the column
}

// TableMetadata represents enrichment data for a table
type TableMetadata struct {
	Table       string
	Description string
}

type OrderedSQL struct {
	SQL            string
	Table          string
	Column         string
	IsTableComment bool
}
