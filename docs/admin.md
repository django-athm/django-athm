# Django Admin

django-athm includes a read-only admin interface for viewing transactions and managing webhooks.

## Accessing the Admin

The admin views are automatically registered. Access at `/admin/django_athm/`.

## Payments

View and search payment records.

**List display**: ecommerce_id, reference_number, status, total, refunded amount, date, customer

**Filters**: status, created_at, transaction_date

**Search**: reference_number, ecommerce_id, business_name, customer info, metadata

### Processing Refunds

1. Select one or more payments with the checkbox
2. Choose **Refund selected payments** from the action dropdown
3. Confirm the refund

Only completed payments with refundable amounts can be refunded.

## Refunds

View refund records linked to payments.

**List display**: reference_number, payment link, amount, status, date, customer

**Filters**: status, transaction_date, created_at

**Search**: reference_number, payment reference_number, customer info

## Webhook Events

View and manage webhook events received from ATH Móvil.

**List display**: id, event_type, processed status, payment link, refund link, remote_ip, date

**Filters**: event_type, processed, created_at

**Search**: id, payment info, refund info, remote_ip, idempotency_key

### Installing Webhooks

1. Navigate to **Webhook Events** in the admin
2. Click **Install Webhooks** button
3. Verify the auto-detected URL
4. Click **Submit**

### Reprocessing Events

To reprocess failed webhook events:

1. Select events with the checkbox
2. Choose **Reprocess selected events** from the action dropdown
3. Confirm

!!! note
    Successfully processed events cannot be reprocessed due to idempotency.

## Clients

View customer records identified by phone number.

**List display**: phone_number, name, email, payment count, refund count, date

**Filters**: created_at, updated_at

**Search**: phone_number, name, email

Client records show the total number of payments and refunds for each customer.
