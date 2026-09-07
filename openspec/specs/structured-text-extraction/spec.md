# Structured Text Extraction Specification

## Purpose

Enable API clients to extract caller-defined structured information from multiple texts through a single, validated request and receive ordered results.

## Requirements

### Requirement: Batch extraction request
The system SHALL accept `POST /entities` requests whose JSON body contains a non-empty `texts` array of non-empty strings and a `schema` containing a valid JSON Schema with an object at its root.

#### Scenario: Valid request
- **WHEN** a client submits one or more non-empty texts and a valid object JSON Schema
- **THEN** the system accepts the request for extraction

#### Scenario: Malformed JSON
- **WHEN** a client submits a body that is not valid JSON
- **THEN** the system responds with HTTP 400 and a JSON error description

#### Scenario: Invalid request fields
- **WHEN** `texts` is missing, empty, contains a non-string or empty string, or `schema` is missing
- **THEN** the system responds with HTTP 422 and a JSON error description without invoking extraction

#### Scenario: Invalid or unsupported schema
- **WHEN** the supplied schema is invalid, does not describe an object at its root, or uses a construct the extraction service does not support
- **THEN** the system responds with HTTP 422 and a JSON error description without invoking extraction

### Requirement: Schema-driven extraction
The system SHALL extract one JSON object from each submitted text using the supplied schema as the required shape and validation contract.

#### Scenario: Extract requested properties
- **WHEN** a valid request asks for properties that can be determined from a text
- **THEN** the corresponding result contains those properties with values conforming to their declared schema types

#### Scenario: Apply one schema to every text
- **WHEN** a valid request contains multiple texts
- **THEN** the system applies the same supplied schema independently to every text

### Requirement: Ordered batch response
The system SHALL respond to a successful extraction with HTTP 200 and a JSON object containing a `results` array whose items are the extracted objects in the same order as the submitted texts.

#### Scenario: Multiple successful extractions
- **WHEN** extraction succeeds for every text in a request
- **THEN** `results` contains exactly one schema-valid object for each text at the matching array position

#### Scenario: Single successful extraction
- **WHEN** extraction succeeds for a request containing one text
- **THEN** `results` contains exactly one schema-valid object

### Requirement: Atomic extraction failure
The system SHALL return no partial extraction results when the extraction provider fails or produces an object that does not conform to the supplied schema.

#### Scenario: Provider failure
- **WHEN** the extraction provider cannot complete any item in the batch
- **THEN** the system responds with HTTP 502 and a JSON error description without a `results` field

#### Scenario: Nonconforming provider output
- **WHEN** an extracted object fails validation against the supplied schema
- **THEN** the system responds with HTTP 502 and a JSON error description without a `results` field
