TAG := 693f55f2-e0e7-4624-8f8f-5f0bf01e51dd

.PHONY: build build-dev build-claude claude bash

build: build-dev build-claude

build-dev:
	docker build -f Dockerfile.dev -t hodoku-dev:$(TAG) .

build-claude: build-dev
	docker build -f Dockerfile.claude -t hodoku-claude:$(TAG) .

claude:
	./claude.sh

bash:
	./claude.sh --bash
