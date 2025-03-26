# FAIRGAME: a Framework for AI Agents Bias Recognition using Game Theory

FAIRGAME is a framework designed to simulate a diverse range of scenarios, from classic Game Theory models to real-world use cases, while identifying biases related to language, cultural traits, or gaming strategies. It enables comprehensive simulations involving AI agents with varying identities and personalities, quantifying the outcomes of their interactions and aligning them with desired results through game-theoretic principles. This makes FAIRGAME a versatile tool for testing and evaluating chatbot behavior, AI decision-making, and agent interactions in various contexts.

## Code Repository Structure

The following tree shows the list of the repository's sections and their main contents:

```
└── apy.py             # Flask API for local testing and interaction
└── Dockerfile         # Containerization setup
└── main.py            # Entry point script to run the core application. It also provides an example of the input
└── resources/         # Static resources (JSON config files and templates)
└── results/           # Stores output results, logs, or evaluation metrics
└── src/               # Core source code: models, logic, and processing pipelines
└── unit_tests/        # Unit tests to verify the functionality of components
```

## Requirements

Your project needs the following keys in the .env file (an example is provided in .env.example):

- API_KEY_OPENAI to properly connect to OpenAI's API and models.
- API_KEY_MISTRAL to properly connect to Mistral's API and models.
- API_KEY_ANTHROPIC to properly connect to Anthropic's API and models.

Optionally, to enable saving results to an S3-compatible storage, you can also include:
- S3_ENDPOINT
- S3_KEY
- S3_SECRET
- BUCKET_NAME

## Governance and Contribution

The development and community management of this project follows the governance rules described in the [GOVERNANCE.md](GOVERNANCE.md) document.

At SOM Research Lab we are dedicated to creating and maintaining welcoming, inclusive, safe, and harassment-free development spaces. Anyone participating will be subject to and agrees to sign on to our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

This project is developed by the AI Readiness and Assessment (AIRA) group at Luxembourg Institute of Science and Technology (LIST) and part of the AI Sandbox (https://ai-sandbox.list.lu/). 
We are open to contributions from the community. Any comment is more than welcome! If you are interested in contributing to this project, please read the [CONTRIBUTING.md](CONTRIBUTING.md) file.


## License

[[License: Apache License Version 2.0]](http://www.apache.org/licenses/)

The source code for the site is licensed under the Apache License Version 2.0, which you can find in the LICENSE file.