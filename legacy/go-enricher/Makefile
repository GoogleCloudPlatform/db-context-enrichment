# Go parameters
GOCMD=go
GOBUILD=$(GOCMD) build
GOCLEAN=$(GOCMD) clean
GOTEST=$(GOCMD) test
GOGET=$(GOCMD) get
BINARY_NAME=db_schema_enricher
BINARY_UNIX=$(BINARY_NAME)_unix

all: test build

build: deps
	GOOS=$(shell go env GOOS) GOARCH=$(shell go env GOARCH) $(GOBUILD) -o $(BINARY_NAME) -v .
	chmod +x $(BINARY_NAME)

test: deps
	$(GOTEST) -v ./...

clean:
	$(GOCLEAN)
	rm -f $(BINARY_NAME)
	rm -f $(BINARY_UNIX)

run: build
	./$(BINARY_NAME) $(ARGS)

deps:
	$(GOGET) -v ./...

# Cross compilation
build-linux: deps
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GOBUILD) -o $(BINARY_UNIX) -v .
	chmod +x $(BINARY_UNIX)

install: build
	go install ./cmd

.PHONY: all build test clean run deps build-linux install