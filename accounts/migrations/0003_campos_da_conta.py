from django.db import migrations, models


class Migration(migrations.Migration):
    """Só esquema. `sub` e `updated_at` nascem anuláveis, sem default e sem `unique`: um
    AddField com `default=uuid.uuid4` calcula o valor uma vez e o dá a todas as linhas, e a
    restrição única falharia. Os valores vêm na 0004, e as restrições na 0005."""

    dependencies = [
        ("accounts", "0002_email_em_minusculas"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="sub",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="updated_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="nickname",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="user",
            name="email_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="email_verificado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="senha_alterada_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="desativada_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="desativada_por",
            field=models.CharField(
                blank=True,
                choices=[("propria_pessoa", "a própria pessoa"), ("admin", "admin")],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="termos_versao",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="user",
            name="termos_aceitos_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
