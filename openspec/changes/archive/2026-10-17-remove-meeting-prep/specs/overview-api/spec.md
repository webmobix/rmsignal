## REMOVED Requirements

### Requirement: Meeting prep
**Reason**: Its content (actions due, KYC review dates, latest RM note) is already available per client and per portfolio through the client, call sheet and actions endpoints, so the overview no longer duplicates it.
**Migration**: Read actions from `actions`, the KYC date from `GET /api/clients` or `GET /api/clients/{client_id}`, and notes from the call sheet or the client detail.
