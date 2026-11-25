# Next Deal — Comprehensive Documentation

L’[application habitation Next-BH](docs/HOUSING_RUNTIME.md) permet de créer des dossiers simulés, valider des brouillons sourcés et reprendre les échanges après un redémarrage. Le guide couvre aussi la construction du catalogue et l’entraînement de la politique.

Le [suivi d’avancement de Next-BH](docs/AVANCEMENT.md) décrit le périmètre livré, l’architecture du pilote de recommandation, les preuves Jira et GitHub, et les travaux restants. Le [prompt du rapport en français](docs/PROMPT_RAPPORT_AVANCEMENT.md) précise les fichiers à produire et les captures à réunir.

## Supported local workflows

Use the housing application above for simulated individual cases with persistent review. Use the [staging runbook](docs/STAGING_SETUP.md) for the separate company recommendation and draft review pilot. Both workflows use synthetic inputs and produce zero outbound customer messages. [Architecture inventory and roadmap](https://github.com/naderite/Next-BH/pull/17)

---

## Original Next Deal prototype

The original prototype contains a Python worker, a FastAPI opportunity service, MongoDB storage, retrieval, and Gmail ingestion helpers. The historical React and Express dashboard is available through the [pilot export](docs/DASHBOARD_SOURCE.md). Kafka and Kafka Connect are infrastructure configuration. The original worker and its external integrations require separate data, configuration, and validation.

- **AI Agent Orchestration:** Central logic for managing conversations, generating responses, and coordinating with other modules.
- **RAG (Retrieval-Augmented Generation):** Semantic search over legal and product documents to enrich AI responses.
- **Intent Analysis:** Hybrid rule-based and ML-powered detection of user intent and product interest.
- **API Datasets (FastAPI):** Microservices for recommendations, guarantees, invoices, and renewals.
- **MongoDB Integration:** Persistent storage for clients, conversations, and messages.
- **Email Integration:** Gmail polling and reply intake helpers.
- **Web Frontend (React/TypeScript):** Admin dashboard for analytics, validation, and client management.
- **Backend (Node.js/Express):** RESTful API, business logic, and security middleware.
- **Kafka Pipeline:** Standalone Kafka and Kafka Connect service definitions.
- **Configuration & Utilities:** Shared constants, helpers, and connectors.

---

## Component Interactions

### High-Level Architecture Diagram

![Next Deal Architecture](./docs/architecture-diagram-1.png)

*This diagram illustrates the flow of data and interactions between the main components: LLM, RAG, MongoDB, FastAPI, and the agent core.*

---

### 1. **AI Agent Orchestration**

- **Location:** [`agent/agent.py`](agent/agent.py), [`agent/app.py`](agent/app.py)
- **Function:** Orchestrates the entire conversation lifecycle, leveraging LLMs via [`agent/utils/llm_utils.py`](agent/utils/llm_utils.py).
- **Data Flow:** 
  - Fetches user profiles and recommendations from FastAPI microservices.
  - Retrieves conversation history and status from MongoDB.
  - Injects RAG context and intent analysis into LLM prompts for tailored responses.
  - Logs all interactions for compliance and validation.

### 2. **Retrieval-Augmented Generation (RAG)**

- **Location:** [`agent/rag_model/rag.py`](agent/rag_model/rag.py), [`agent/rag_model/document-parseer.py`](agent/rag_model/document-parseer.py)
- **Function:** Parses and embeds PDFs/CSVs into ChromaDB for semantic search.
- **Usage:** Agent queries RAG for relevant legal/product context, which is dynamically injected into LLM prompts.

### 3. **Intent Analysis**

- **Location:** [`agent/intent_analysis/intent_analysis.py`](agent/intent_analysis/intent_analysis.py)
- **Function:** Detects user intent and product mentions using both rule-based patterns and transformer models.
- **Usage:** Guides agent decision-making for recommendations, escalation, and workflow routing.

### 4. **API Datasets (FastAPI)**

- **Location:** [`api_datasets/app.py`](api_datasets/app.py)
- **Function:** Serves as the backend for product, guarantee, invoice, and renewal recommendations.
- **Usage:** Queried by the agent for real-time, personalized suggestions.

### 5. **MongoDB Integration**

- **Location:** [`agent/utils/mongodb_conn.py`](agent/utils/mongodb_conn.py), backend models
- **Function:** Stores all persistent data (clients, conversations, messages, validation status).
- **Usage:** Enables robust tracking, auditing, and validation workflows.

### 6. **Email Integration**

- **Location:** [`agent/utils/mail_reciever.py`](agent/utils/mail_reciever.py)
- **Function:** Automates email ingestion, reply handling, and synchronization with MongoDB.
- **Usage:** Ensures multi-channel engagement and seamless conversation tracking.

### 7. **Web Frontend**

- **Location:** [`frontend/` in the verified dashboard snapshot](https://github.com/roudayn-kouka/BH-Assurance/tree/a18e1e0fc402af64d63a16fba5532bc357d077e1/frontend)
- **Function:** Provides dashboards for analytics, validation, and client management.
- **Usage:** Admins review, edit, and approve AI-generated responses; monitor KPIs and workflow status.

### 8. **Backend (Node.js/Express)**

- **Location:** [`backend/` in the verified dashboard snapshot](https://github.com/roudayn-kouka/BH-Assurance/tree/a18e1e0fc402af64d63a16fba5532bc357d077e1/backend)
- **Function:** REST API for clients, conversations, messages, and email webhooks; implements security and business logic.
- **Usage:** Serves the historical dashboard. See its source for route and middleware configuration.

### 9. **Kafka Pipeline**

- **Location:** [`pipeline/kafka/docker-compose.yml`](pipeline/kafka/docker-compose.yml), [`entrypoint.sh`](entrypoint.sh), [`plugins.sh`](plugins.sh)
- **Function:** Defines standalone Kafka and Kafka Connect services. The checked-in application paths use direct database or HTTP calls.

---

## Workflow Overview

### Process Flow Diagram

![Next Deal Process Flow](./docs/architecture-diagram-2.png)

*This diagram shows the step-by-step workflow from receiving a client message to generating and validating an AI response.*

---

## Deployment & Operations

For a local walkthrough with synthetic data, see the [company recommendation demo](docs/RECOMMENDATION_DEMO.md).

The [human review demo](docs/DRAFT_REVIEW_DEMO.md) covers the isolated dashboard. The [Wave 3 staging runbook](docs/STAGING_PILOT.md) covers the full synthetic recommendation and review pilot, including its documented CI results and live staging acceptance criteria.

### Historical platform

The original worker depends on prepared opportunity CSVs, model services, MongoDB and external documents. The repository provides reproducible runbooks for the two synthetic workflows above. See the [dashboard source notes](docs/DASHBOARD_SOURCE.md) for the verified export and the historical gitlink.

---

## Human review

The company pilot saves drafts as pending in disposable MongoDB and records reviewer decisions in the dashboard. The housing application persists review decisions and simulated outcomes separately in SQLite. Housing reviewer names are local form input. Shared deployment requires authenticated reviewer accounts, persistent storage and restore checks.

---

## Extensibility & Customization

- **Product Expansion:** Update product keywords and recommendation logic in `intent_analysis.py` and FastAPI endpoints.
- **Channel Integration:** Add Kafka connectors or webhook handlers for new communication channels (SMS, WhatsApp, etc.).
- **Prompt Engineering:** Refine prompt templates in `config.py` for improved LLM performance and multilingual support.
- **Analytics:** Extend frontend dashboards to visualize new KPIs or workflow metrics.

---

## Best Practices

- **Separation of Concerns:** Each module is self-contained and communicates via well-defined interfaces.
- **Scalability:** Kafka and Docker Compose enable horizontal scaling and future integrations.
- **Auditability:** All critical actions are logged and traceable.
- **Validation:** Human-in-the-loop workflows ensure AI outputs meet business and regulatory standards.

---

## License

This project is proprietary to BH Assurance. For usage, extension, or partnership inquiries, contact the project owner.

---

## Support & Contact

For technical support, feature requests, or bug reports, please contact the project maintainer or use the internal ticketing system.

---

## Appendix: Directory Structure

```
agent/
  ├── agent.py
  ├── app.py
  ├── config.py
  ├── rag_model/
  ├── intent_analysis/
  ├── utils/
web/
  ├── BH-Assurance/
      ├── backend/
      ├── frontend/
pipeline/
  ├── kafka/
      ├── docker-compose.yml
```

---

**Next Deal** is designed for reliability, compliance, and extensibility. For further documentation, see inline code comments and module docstrings.
