# Reconciliation

The `athm_sync` management command reconciles local payment records with ATH Móvil's Transaction Report API.

## When to Use

- Recover missed webhooks
- Backfill historical transaction data
- Audit local records against ATH Móvil
- Initial data import when setting up django-athm

## Usage

```bash
python manage.py athm_sync --from-date 2025-01-01 --to-date 2025-01-31
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--from-date` | Yes | Start date (YYYY-MM-DD) |
| `--to-date` | Yes | End date (YYYY-MM-DD) |
| `--dry-run` | No | Preview changes without modifying database |

## Dry Run Mode

Preview what would be created or updated:

```bash
python manage.py athm_sync --from-date 2025-01-01 --to-date 2025-01-31 --dry-run
```

## What It Does

1. Fetches all transactions from ATH Móvil for the date range
2. Filters to eCommerce COMPLETED transactions only
3. For each transaction:
   - **New payment**: Creates `Payment` record
   - **Existing payment**: Updates missing fields (fee, net_amount, customer info)
   - **Complete payment**: Skips (already synced)
4. Creates/updates `Client` records based on phone numbers

## Example Output

```
ATH Móvil Sync
========================================
Date range: 2025-01-01 to 2025-01-31
Fetched 47 transactions

Processing 42 eCommerce COMPLETED transactions

Created: 3
Updated: 5
Skipped: 34
Errors: 0

Sync completed successfully.
```

## Scheduling Periodic Sync

For production, schedule daily sync via cron or task queue:

```bash
# Cron example: sync yesterday's transactions at 6 AM
0 6 * * * cd /path/to/project && python manage.py athm_sync \
    --from-date $(date -d "yesterday" +\%Y-\%m-\%d) \
    --to-date $(date -d "yesterday" +\%Y-\%m-\%d)
```

!!! note
    Webhooks are the primary data source. Use `athm_sync` as a backup for missed webhooks, not as the primary sync mechanism.
