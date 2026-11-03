FinWise AI Frontend (Connected)
===============================

This is the existing FinWise dashboard design updated to call the current Flask backend.

Run backend first
-----------------
1. Start the backend from your updated backend folder:
   python app.py
2. Verify http://127.0.0.1:5000/api/health returns status "ok".

Run frontend
------------
Open this folder in VS Code and launch index.html using Live Server.
Typical address: http://127.0.0.1:5500

Features connected
------------------
- Register and sign in using the Flask JWT API.
- Loads the current user's dashboard totals, transactions, loans, and bank connections.
- Add transaction and add loan forms save to the backend database.
- Loan simulator calls POST /api/simulator.
- Connect demo bank and sync synthetic transactions.
- Search filters visible transaction rows.
- Sign out removes the locally stored JWT.

API configuration
-----------------
Default API base: http://127.0.0.1:5000/api
Change API_BASE at the top of script.js if your backend uses another address.

Important limitations
---------------------
- Bank connection is a simulation only; no real bank or SMS data is accessed.
- The backend dashboard totals include all saved transactions, not only the selected month.
- The AI assistant is not connected to an LLM.
- Authentication token is stored in localStorage for this prototype; this is not the preferred storage design for a production financial app.
- If registration/login fails, inspect the Flask terminal and browser Developer Tools > Console/Network.
