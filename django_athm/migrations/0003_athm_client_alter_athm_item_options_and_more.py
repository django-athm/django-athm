# Generated by Django 4.1 on 2022-08-05 13:51

import uuid

import django.db.models.deletion
from django.db import migrations, models

import django_athm.models


class Migration(migrations.Migration):

    dependencies = [
        ("django_athm", "0002_auto_20200202_1855"),
    ]

    operations = [
        migrations.CreateModel(
            name="ATHM_Client",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=512)),
                ("email", models.EmailField(blank=True, max_length=254)),
                (
                    "phone_number",
                    models.CharField(
                        blank=True,
                        max_length=32,
                        validators=[django_athm.models.validate_phone_number],
                    ),
                ),
            ],
            options={
                "verbose_name": "ATH Móvil Client",
                "verbose_name_plural": "ATH Móvil Clients",
            },
        ),
        migrations.AlterModelOptions(
            name="athm_item",
            options={
                "verbose_name": "ATH Móvil Item",
                "verbose_name_plural": "ATH Móvil Items",
            },
        ),
        migrations.AlterModelOptions(
            name="athm_transaction",
            options={
                "verbose_name": "ATH Móvil Transaction",
                "verbose_name_plural": "ATH Móvil Transactions",
            },
        ),
        migrations.AddField(
            model_name="athm_transaction",
            name="fee",
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name="athm_transaction",
            name="message",
            field=models.CharField(blank=True, max_length=512, null=True),
        ),
        migrations.AlterField(
            model_name="athm_item",
            name="transaction",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                related_query_name="item",
                to="django_athm.athm_transaction",
            ),
        ),
        migrations.AlterField(
            model_name="athm_transaction",
            name="date",
            field=models.DateTimeField(blank=True),
        ),
        migrations.AlterField(
            model_name="athm_transaction",
            name="status",
            field=models.CharField(
                choices=[
                    ("processing", "processing"),
                    ("completed", "completed"),
                    ("refunded", "refunded"),
                ],
                default="processing",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="athm_transaction",
            name="client",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="transactions",
                related_query_name="transaction",
                to="django_athm.athm_client",
            ),
        ),
    ]
