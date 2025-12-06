# Generated manually for v1.0.0-beta1

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_athm", "0003_athm_client_alter_athm_item_options_and_more"),
    ]

    operations = [
        # Create WebhookEvent model
        migrations.CreateModel(
            name="ATHM_WebhookEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "webhook_id",
                    models.CharField(
                        max_length=255,
                        unique=True,
                        db_index=True,
                        help_text="Unique webhook delivery ID for idempotency",
                    ),
                ),
                (
                    "remote_ip",
                    models.GenericIPAddressField(
                        help_text="IP address of the webhook request"
                    ),
                ),
                (
                    "headers",
                    models.JSONField(
                        default=dict, help_text="HTTP headers from the webhook request"
                    ),
                ),
                ("body", models.TextField(help_text="Raw webhook payload")),
                (
                    "valid",
                    models.BooleanField(
                        default=False, help_text="Whether the webhook passed validation"
                    ),
                ),
                (
                    "processed",
                    models.BooleanField(
                        default=False,
                        help_text="Whether the webhook was successfully processed",
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("payment_received", "Payment Received"),
                            ("donation_received", "Donation Received"),
                            ("refund_sent", "Refund Sent"),
                            ("ecommerce_completed", "eCommerce Payment Completed"),
                            ("ecommerce_cancelled", "eCommerce Payment Cancelled"),
                            ("ecommerce_expired", "eCommerce Payment Expired"),
                            ("unknown", "Unknown"),
                        ],
                        default="unknown",
                        help_text="Type of webhook event",
                        max_length=32,
                    ),
                ),
                (
                    "transaction_status",
                    models.CharField(
                        blank=True,
                        help_text="Transaction status from webhook",
                        max_length=16,
                    ),
                ),
                ("exception", models.CharField(blank=True, max_length=255)),
                ("traceback", models.TextField(blank=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("modified", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "ATH Móvil Webhook Event",
                "verbose_name_plural": "ATH Móvil Webhook Events",
                "ordering": ["-created"],
            },
        ),
        # Update Transaction model options
        migrations.AlterModelOptions(
            name="athm_transaction",
            options={
                "ordering": ["-created"],
                "verbose_name": "ATH Móvil Transaction",
                "verbose_name_plural": "ATH Móvil Transactions",
            },
        ),
        # Add new Transaction fields
        migrations.AddField(
            model_name="athm_transaction",
            name="business_name",
            field=models.CharField(
                blank=True, help_text="Business name from ATH Móvil", max_length=255
            ),
        ),
        migrations.AddField(
            model_name="athm_transaction",
            name="created",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="athm_transaction",
            name="customer_name",
            field=models.CharField(
                blank=True, help_text="Customer name from ATH Móvil", max_length=255
            ),
        ),
        migrations.AddField(
            model_name="athm_transaction",
            name="customer_phone",
            field=models.CharField(
                blank=True, help_text="Customer phone number", max_length=32
            ),
        ),
        migrations.AddField(
            model_name="athm_transaction",
            name="daily_transaction_id",
            field=models.CharField(
                blank=True,
                help_text="ATH Móvil daily transaction ID",
                max_length=64,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="athm_transaction",
            name="ecommerce_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Unique ecommerce transaction identifier",
                max_length=64,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="athm_transaction",
            name="modified",
            field=models.DateTimeField(auto_now=True),
        ),
        # Alter Item fields
        migrations.AlterField(
            model_name="athm_item",
            name="description",
            field=models.CharField(
                blank=True, help_text="Item description", max_length=255
            ),
        ),
        migrations.AlterField(
            model_name="athm_item",
            name="name",
            field=models.CharField(help_text="Item name", max_length=128),
        ),
        migrations.AlterField(
            model_name="athm_item",
            name="price",
            field=models.DecimalField(
                decimal_places=2, help_text="Item price", max_digits=10
            ),
        ),
        migrations.AlterField(
            model_name="athm_item",
            name="tax",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Item tax",
                max_digits=10,
                null=True,
            ),
        ),
        # Alter Transaction fields
        migrations.AlterField(
            model_name="athm_transaction",
            name="client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="transactions",
                related_query_name="transaction",
                to="django_athm.athm_client",
            ),
        ),
        migrations.AlterField(
            model_name="athm_transaction",
            name="date",
            field=models.DateTimeField(
                blank=True,
                help_text="Transaction completion date from ATH Móvil",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="athm_transaction",
            name="fee",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="ATH Móvil processing fee",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="athm_transaction",
            name="reference_number",
            field=models.CharField(
                db_index=True,
                help_text="ATH Móvil reference number for completed transactions",
                max_length=64,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="athm_transaction",
            name="refunded_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Amount refunded",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="athm_transaction",
            name="status",
            field=models.CharField(
                choices=[
                    ("open", "Open"),
                    ("confirm", "Confirmed"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                    ("expired", "Expired"),
                    ("refunded", "Refunded"),
                ],
                db_index=True,
                default="open",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="athm_transaction",
            name="subtotal",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Subtotal before tax",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="athm_transaction",
            name="tax",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Tax amount",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="athm_transaction",
            name="total",
            field=models.DecimalField(
                decimal_places=2, help_text="Total transaction amount", max_digits=10
            ),
        ),
        # Add indexes
        migrations.AddIndex(
            model_name="athm_transaction",
            index=models.Index(
                fields=["-created"], name="django_athm_created_d0a3f3_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="athm_transaction",
            index=models.Index(
                fields=["status", "-created"], name="django_athm_status_52f47e_idx"
            ),
        ),
        # Add WebhookEvent transaction relationship
        migrations.AddField(
            model_name="athm_webhookevent",
            name="transaction",
            field=models.ForeignKey(
                blank=True,
                help_text="Associated transaction if found/created",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="webhook_events",
                to="django_athm.athm_transaction",
            ),
        ),
        # Add WebhookEvent indexes
        migrations.AddIndex(
            model_name="athm_webhookevent",
            index=models.Index(
                fields=["-created"], name="django_athm_created_211024_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="athm_webhookevent",
            index=models.Index(
                fields=["valid", "processed"], name="django_athm_valid_f40b38_idx"
            ),
        ),
    ]
