# Statistics 101 Tutor with Mem0

I wanted to take the online cookbook a step further and built a basic stats tutor as a conduit to answer the question: are managed memory solutions for LLMs worth it?

## Verdict
No. 

## How it works
There are two modes:
  - **Interactive Learning Mode**: Natural conversation with the tutor about statistics concepts
    - As you converse, the tutor will persist the concepts you discuss in memory
  - **Smart Testing Mode**: 
    - Generates contextual test questions based on previous interactions
    - Provides detailed feedback on answers
    - Uses spaced repetition to optimize learning


## Installation

1. Use poetry to install dependencies
```bash
poetry shell
poetry install
``` 

2. Set up environment variables:
```bash
cp .env.example .env
```


## Usage

Run the tutor:
```bash
python src/main.py
```


## Testing

Run the test suite:
```bash
pytest tests/
```

