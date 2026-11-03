# FinWise bank integration: current scope

**What is implemented:** a demo-only connection/consent record, simulated transaction sync, idempotency ledger, connection listing, and local revocation.

**What is not implemented:** real bank login, SMS reading, Account Aggregator APIs, provider tokens, live callbacks, or real transaction retrieval.

## Test with PowerShell

First start the server and register a user:

```powershell
$body = @{ name = "Demo User"; email = "demo@example.com"; password = "StrongPassword123" } | ConvertTo-Json
$auth = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/auth/register -ContentType "application/json" -Body $body
$token = $auth.access_token
$headers = @{ Authorization = "Bearer $token" }
```

Create a demo connection:

```powershell
$conn = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/bank/demo/connect -Headers $headers
$conn.connection
```

Sync simulated data (replace `1` with the returned connection ID):

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/bank/connections/1/sync -Headers $headers
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:5000/api/transactions -Headers $headers
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:5000/api/dashboard -Headers $headers
```

Revoke the connection:

```powershell
Invoke-RestMethod -Method Delete -Uri http://127.0.0.1:5000/api/bank/connections/1 -Headers $headers
```

Repeated syncs skip duplicates. The sample amounts and descriptions are synthetic.
