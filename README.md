# Statistics 101 Tutor with Mem0

I wanted to take the online cookbook a step further and built a basic stats tutor as a conduit to answer the question: is mem0's managed memory solution worth it?

## Observations
- (+) The API dashboard is easy to use and understand
- (+) The processed memory captures the salient details of the conversation I throw at it
- (-) Did not an answer to a simple question I asked Discord (this is a prod at their community management)
- (-) You delegate every memory decision to mem0. It decides whether something is a duplicate, or presenting contradicting information that necessitates an update or whether something is even worth adding to memory. 

For this specific application, it was poor at determining what was worth adding to memory. I had to explicitly appended something like "please note xyz" "this is important to remember" to the user prompt. I would extrapolate this and guess that most contexts, the user would seldom signal this in their message - and it's on the developer to ensure their program has a good way to determine if an interaction is worth persisting.

For example asking the tutor 'teach me the difference between mean and median' did not result in a memory being added.

- (-) There's no self-serve pricing at the time of writing which I take as a sign of high vendor risk
- (-) The API seems bloated (putting Orgs and Members as first class citizens) and prone to breakage, again downstream of the early nature of the product.
- (-) The update API only supports updating the memory itself, not the metadata. This was annoying because I wanted to use it to capture the notion of a "last_tested" timestamp to enable spaced repetition.


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

