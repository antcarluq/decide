# Generated by Django 2.0 on 2020-01-04 23:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voting', '0004_auto_20191206_1316'),
    ]

    operations = [
        migrations.AddField(
            model_name='voting',
            name='end_date_selected',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='voting',
            name='start_date_selected',
            field=models.DateTimeField(null=True),
        ),
    ]
