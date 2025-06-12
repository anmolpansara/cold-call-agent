# Cold Call Agent Demo

## Prerequisites

- Python 3.9 or higher
- Git
- Virtual environment tools (e.g., `venv` or `virtualenv`)

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-repo-name/cold-call-agent.git
   cd cold-call-agent

2. **Create and Activate a Virtual Environment**:
python -m venv .venv
source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`

3. **Install Dependencies:**:
    ```bash
    pip install -r requirements.txt

4. **Set Environment Variables:**:
 Create a .env file in the root directory and add the variables copy from .env.local

5. **Running the Application**:
FastAPI backend:
    ```bash
    python call.py

Streamlit frontend:
    ```bash
    streamlit run main.py 

Start the Agent Worker:
    ```bash
    python outbound_call_agent.py dev

## Using the CSV Upload Feature

The application supports bulk contact uploads via CSV files. Your CSV should have at least the following columns:

- `name`: The customer's full name
- `phone`: The phone number with country code (e.g., +14155552671)

Optional columns that may enhance the calling experience:
- `company`: Customer's company name
- `industry`: Customer's industry for more targeted conversations

A sample CSV file (`sample_contacts.csv`) is provided in the repository.