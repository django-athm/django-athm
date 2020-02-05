# Generated by Django 2.2.9 on 2020-02-02 18:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_athm", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="athm_item",
            options={"verbose_name": "ATHM Item", "verbose_name_plural": "ATHM Items"},
        ),
        migrations.AlterModelOptions(
            name="athm_transaction",
            options={
                "verbose_name": "ATHM Transaction",
                "verbose_name_plural": "ATHM Transactions",
            },
        ),
        migrations.AlterField(
            model_name="athm_item",
            name="metadata",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name="athm_transaction",
            name="metadata_1",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name="athm_transaction",
            name="metadata_2",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]